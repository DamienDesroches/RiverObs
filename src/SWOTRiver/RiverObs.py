"""
A class for holding all of the river observations associated with a reach.
Observations are broken up into RiverNodes, each node associated with
a center line point.

The class supports extracting summary observations from each node and
returning them for analaysis (e.g., fitting).
"""

from collections import OrderedDict as odict
import numpy as N
from Centerline import Centerline
from RiverNode import RiverNode

class RiverObs:
    """A class for holding all of the river observations associated with a reach.
    Observations are broken up into RiverNodes, each node associated with
    a center line point.

    The class supports extracting summary observations from each node and
    returning them for analaysis (e.g., fitting)."""

    def __init__(self,reach,xobs,yobs,k=3,ds=None,max_width=None,minobs=1):
        """Initialize with a reach variable (e.g., from ReachExtractor),
        and a set of observation coordinates.

        reach: has reach.x,reach.y (and optionally, reach.metadata).
        xobs, yobs: iterables with observation coordinates.
        k: centerline spline smoothing degree (default 3)
        ds: centerline point separation (default None)
        max_width: if !=None, exclude all observations more than max_width/2
                   away from the centerline in the normal direction
        minobs: minimum number of observations for each node.
        """

        # Copy metadata, in case it is present
        
        try:
            self.metadata = reach.metadata
        except:
            self.metadata = None

        self.ndata = len(xobs)
            
        # Calculate the centerline for this reach

        self.centerline = Centerline(reach.x,reach.y,k=k,ds=ds)
        print('Centerline initialized')

        # Calculate the local coordiantes for each observation point
        # index: the index of the nearest point
        # d: distance to the point
        # x,y: The coordiantes of the nearest point
        # s,n: The along and across track coordinates of the point
        # relative to the nearest point coordinate system.

        self.index,self.d,self.x,self.y,self.s,self.n = self.centerline(xobs,yobs)
        print('Local coordiantes calculated')

        # Assign to each point the actual along-track distance, not just the delta s

        self.s += self.centerline.s[self.index]

        # Edit, so that only river points appear

        if max_width != None:
            self.in_channel = self.flag_out_channel(max_width)
        self.max_width = max_width
        self.nedited_data = len(self.x)

        # Get the mapping from observation to node position (1 -> many); i.e., the inverse
        # of index (many -> 1), which maps node position to observations

        self.minobs = minobs
        self.populated_nodes, self.obs_to_node_map = self.get_obs_to_node_map(self.index,self.minobs)

    def flag_out_channel(self,max_width):
        """Get the indexes of all of the points inside a channel of max_width,
        and remove the points from the list of observations."""
         
        self.in_channel = N.abs(self.n) <= max_width/2.

        self.index = self.index[self.in_channel]
        self.d = self.d[self.in_channel]
        self.x = self.x[self.in_channel]
        self.y = self.y[self.in_channel]
        self.s = self.s[self.in_channel]
        self.n = self.n[self.in_channel]

        return self.in_channel

    def get_obs_to_node_map(self,index,minobs=1):
        """Get the mapping from observation to node position (1 -> many); i.e., the inverse
        of index (many -> 1), which maps node position to observations.

        In order for a node to appear, it must have at least minobs observations.
        """

        # Get the list of potential nodes
        
        nodes = N.unique(index)

        self.obs_to_node_map = odict()
        self.nobs = N.zeros(len(self.centerline.x),dtype=N.int32)
        self.populated_nodes = []
        for node in nodes:
            obs_index = N.flatnonzero(index == node)
            nobs = len(obs_index)
            if nobs >= minobs:
                self.populated_nodes.append(node)
                self.obs_to_node_map[node] = obs_index
                self.nobs[node] = nobs

        return self.populated_nodes, self.obs_to_node_map

    def add_obs(self,obs_name,obs):
        """Add an observation as a class variable self.obs_name.
        The observation is edited to remove measurements outside
        the channel.

        obs is an iterable of length self.ndata or self.nedited_data.
        """

        if (len(obs) != self.ndata) and (len(obs) != self.nedited_data):
            raise Exception('Observation size incompatible with initial observations')

        if (self.max_width != None) and (len(obs) == self.ndata):
            obs = obs[self.in_channel]
        
        exec('self.%s = obs'%obs_name)

    def obs_to_node(self,obs,node):
        """Get all of the observations in an array obs which map to a node.

        obs: iterable of the same size as the xobs, yobs 
             or the same size as self.x, self.y. If the same size
             as xobs, the observations will be limited to in channel
             observations, if this has been computed. If the same
             size as self.x, no editing occurs.

        node: node to match

        Returns the observations for that node, or an empty array if there
        are no observations for that node.
        """

        if not (int(node) in self.populated_nodes):
            return N.array([])

        # If only certain observations have been kept, get the edited vector
        
        if (self.max_width != None) and (len(obs) == self.ndata):
            obs = obs[self.in_channel] 

        return N.asarray(obs)[self.obs_to_node_map[node]]

    def load_nodes(self,vars=[]):
        """Load the desired variables into each of the populated nodes.

        All of the vars should have been loaded previously with add_obs.
        """

        if type(vars) == str:
            vars = [vars]

        self.river_nodes = odict()

        for node in self.populated_nodes:
            d = self.obs_to_node(self.d,node)
            x = self.obs_to_node(self.x,node)
            y = self.obs_to_node(self.y,node)
            s = self.obs_to_node(self.s,node)
            n = self.obs_to_node(self.n,node)
            self.river_nodes[node] = RiverNode(node,d,x,y,s,n)
            for var in vars:
                exec('obs = self.obs_to_node(self.%s,node)'%var)
                self.river_nodes[node].add_obs(var,obs,sort=False)

    def get_node_stat(self,stat,var):
        """Get a list of results of applying a given stat to a river node variable.
        
        Both stat and var are strings. var should be the name of an instance variable
        for the river node.
        
        A stat is a member function of the river node which returns a
        result given the variable name.

        Example stats are: 'mean', 'std', 'cdf'
        """

        result = []
        for node, river_node in self.river_nodes.iteritems():
            exec('result.append( river_node.%s("%s") )'%(stat,var) )

        return result
                
                