class BfresOffset:
    def __init__(self, reader):
        self.address = reader.tell()
        self.to_self = reader.read_int32()
        self.to_file = self.address + self.to_self

    def __bool__(self):
        return self.to_self != 0

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.to_file == other.to_file

class BfresNameOffset(BfresOffset):
    def __init__(self, reader):
        super().__init__(reader)
        # Seek to the position (pointing at the start of the 0-terminated string, after the length) and get the string.
        current_pos = reader.tell()
        reader.seek(self.to_file)
        self.name = reader.read_0_string()
        reader.seek(current_pos)

class IndexGroup:
    class Node:
        def __init__(self, reader):
            self.search_value = reader.read_uint32()
            self.left_index = reader.read_uint16()
            self.right_index = reader.read_uint16()
            self.name_offset = BfresNameOffset(reader)
            self.data_offset = BfresOffset(reader)
            self.data = None # Will be loaded via callback when creating the IndexGroup.

    def __init__(self, reader, data_cb):
        # Read the properties of the index group.
        self.length_in_bytes = reader.read_uint32()
        self.node_count = reader.read_uint32() # Excluding the first (root) node.
        # Read the nodes.
        self.nodes = []
        for i in range(0, self.node_count + 1):
            node = self.Node(reader)
            # Seek to the data offset, and run the callback to create the node's data (not for the root node).
            if i > 0:
                current_pos = reader.tell()
                reader.seek(node.data_offset.to_file)
                node.data = data_cb(reader)
                reader.seek(current_pos)
            self.nodes.append(node)

    def __getitem__(self, item):
        # Lookup nodes either by index, name, or data offset.
        if isinstance(item, int):
            return self.nodes[item]
        elif isinstance(item, str):
            for node in self.nodes:
                if node.name_offset.name == item:
                    return node
            raise KeyError("Did not find a node with the given name.")
        elif isinstance(item, BfresOffset):
            for node in self.nodes:
                if node.data_offset == item:
                    return node
            raise KeyError("Did not find a node with the given data offset.")
        else:
            return self.nodes.__getitem__(item)

    def __iter__(self):
        return iter(self.nodes)
