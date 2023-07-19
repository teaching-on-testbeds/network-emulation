from chi.server import create_server

class DuplicateNetwork(Exception):
    pass

class DuplicateSubnet(Exception):
    pass

class DuplicateServer(Exception):
    pass


def ensure_network(conn, network_name, **kwargs):
    """
    Reuse network by name instead of UUID. Searches all networks visible to the current user/project.
    If network does not exist, creates it with kwargs. If it does exist, returns it. If more than one
    network matches, raises an error.
    
    Returns a network object.
    """
    # all_networks = network.list_networks()
    # matching_nets = [n for n in all_networks if n.get("name") == network_name]
        
    matching_nets = list(conn.network.networks(name=network_name))
    
    try:
        if len(matching_nets) == 0:
            network_obj = conn.create_network(
                network_name,
            )
            print(f"created network {network_obj.get('id')}")
        elif len(matching_nets) == 1:
            network_obj = matching_nets[0]
            print(f"reusing network {network_obj.get('id')} with name {network_obj.get('name')}")
        else:
            raise DuplicateNetwork(f"multiple matching networks exist, ensure network_name {network_name} is unique")
    except DuplicateNetwork:
        raise
    else:
        return network_obj
    

    
def ensure_subnet(conn, name, network_id, **kwargs):
    """
    Reuse subnet by name and network id.
    
    Returns a subnet object.
    """
    n_client = conn.network
    
    matching_subnets = list(n_client.subnets(name=name,network_id=network_id))
    if len(matching_subnets) == 0:
        subnet = n_client.create_subnet(
            name=name,
            network_id=network_id,
            **kwargs
        )
        print(f"created subnet {subnet.id}")
        return subnet
    elif len(matching_subnets) == 1:
        subnet = matching_subnets[0]
        print(f"reusing subnet {subnet.id} with properties {subnet}")
        return subnet
    else:
        raise DuplicateSubnet(f"multiple subnets with name {name} exist for network_id {network_id}")
        

def ensure_server(conn, name, **kwargs):
    """
    Reuse server by name
    
    Returns a Server object
    """
    
    nova_client = conn.compute
    
    matching_servers = list(nova_client.servers(name=name))
    if len(matching_servers) == 0:
        server = create_server(name, 
                               **kwargs,
                              )
        print(f"created new server {server.id}")
    elif len(matching_servers) == 1:
        server = matching_servers[0]
        print(f"reusing server {server.id} with properties {server}")
        return server
    else:
        raise DuplicateServer(f"Multiple servers with name {name} exist, please delete or use a different name")