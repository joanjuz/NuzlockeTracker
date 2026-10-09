"""Snapshot comparison belongs to the backend, independent of UI widgets."""
from copy import deepcopy
class SnapshotStore:
    def __init__(self):self.values={}
    def update(self,key,value):
        changed=self.values.get(key)!=value
        if changed:self.values[key]=deepcopy(value)
        return changed
