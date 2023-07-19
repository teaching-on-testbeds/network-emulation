::: {.cell .markdown}
# Emulating network impairments

When we do experiments involving computer networks, we often want to "mimic" specific network scenarios. For example, we might want to "mimic" a satellite wireless network (which tends to have low data rate and very large delay), or a fiber optic wired network link (which tends to have high data rate and small delay). Even when the specific network we want to "mimic" is not available to us for experimentation, we can use a technique called *network emulation* to make any existing network have the desired characteristics.

This notebook will show you how to:

* launch three VMs with network connectivity in a line topology
* attach a public IP address to each VM, so that you can access it over SSH
* configure the VM interfaces on the "experiment" network
* measure the characteristics of the pre-existing network
* emulate different network conditions (packet loss, delay, jitter, data rate) over this link
* delete resources

:::

::: {.cell .markdown}

## Launch three VMs in a line

In this exercise, we will reserve resources on KVM@TACC: two hosts (VMs) on two different network segments, connected by a router (also a VM). 

When we send data from one host to the other, that data will go *through* the router.

:::


::: {.cell .markdown}
First, we load some required libraries:
:::


::: {.cell .code}
``` python
# enable autoreload magic to pull in updated utils.py 
%load_ext autoreload
%autoreload 2
```
:::

::: {.cell .code}
``` python
import openstack
import chi
import chi.ssh
import os 
import utils
# configure openstacksdk for actions unsupported by python-chi
os_conn = chi.clients.connection()
```
:::

::: {.cell .markdown}

We indicate that we’re going to use the KVM@TACC site. We also need to specify the name of the Chameleon "project: that this experiment is part of. The project name will have the format “CHI-XXXXXX”, where the last part is a 6-digit number, and you can find it on your user dashboard.

In the cell below, replace the project ID with your own project ID, then run the cell.

:::


::: {.cell .code}
```python
chi.use_site("KVM@TACC")
PROJECT_NAME = "CHI-XXXXXX"
chi.set("project_name", PROJECT_NAME)
```
:::



::: {.cell .markdown}
Next, we will create three network links:

* One "public" network link, that we will use to connect to our hosts and router via SSH. The network interfaces on this link will have addresses in the range 192.168.10.X, where X is any integer from 1 to 254.
* One "experiment" network link, that will connect the "romeo" host to the router. The network interfaces on this link will have addresses in the range 10.10.1.X, where X is any integer from 1 to 254.
* One "experiment" network link, that will connect the "juliet" host to the router. The network interfaces on this link will have addresses in the range 10.10.2.X, where X is any integer from 1 to 254.

We will make sure the networks have our username as part of the network name, so that we can easily identify them in the KVM@TACC web interface.

:::

::: {.cell .code}
``` python
# create three networks. One will be used for SSH and API access,
# and the other two will be used for experiments. 
# We need to disable port security on those two experiment networks.

username = os.getenv('USER')
public_net = utils.ensure_network(os_conn, network_name="public-net-" + username)
exp_net_1  = utils.ensure_network(os_conn, network_name="exp-net-1-" + username)
exp_net_2  = utils.ensure_network(os_conn, network_name="exp-net-2-" + username)

public_subnet = utils.ensure_subnet(
    os_conn,
    name="public-subnet-" + username,
    network_id=public_net.get("id"),
    ip_version='4',
    cidr="192.168.10.0/24",
    gateway_ip="192.168.10.1"
)

exp_subnet_1 = utils.ensure_subnet(
    os_conn,
    name="exp-subnet-1-" + username,
    network_id=exp_net_1.get("id"),
    ip_version='4',
    cidr="10.10.1.0/24",
    enable_dhcp=True,
    gateway_ip=None
)

exp_subnet_2 = utils.ensure_subnet(
    os_conn,
    name="exp-subnet-2-" + username,
    network_id=exp_net_2.get("id"),
    ip_version='4',
    cidr="10.10.2.0/24",
    enable_dhcp=True,
    gateway_ip=None
)
```
:::


::: {.cell .markdown}

We need to configure the two "experiment" links so that they will carry all traffic between the hosts - we will need to disable the default security settings on them. 

:::


::: {.cell .code}
``` python
netid_1 = chi.network.get_network_id("exp-net-1-" + username)
netid_2 = chi.network.get_network_id("exp-net-2-" + username)
```
:::

::: {.cell .code}
``` python
%%bash -s "$PROJECT_NAME" "$netid_1" "$netid_2"
export OS_PROJECT_NAME=$1
export OS_AUTH_URL=https://kvm.tacc.chameleoncloud.org:5000/v3
export OS_REGION_NAME=KVM@TACC
access_token=$(curl -s -H"authorization: token $JUPYTERHUB_API_TOKEN" "$JUPYTERHUB_API_URL/users/$JUPYTERHUB_USER" | jq -r .auth_state.access_token)
export OS_ACCESS_TOKEN="$access_token"

openstack network set --disable-port-security $2
openstack network set --disable-port-security $3
```
:::


::: {.cell .markdown}

Now, we will create the three VMs - romeo, juliet, and router, with a network interface on the appropriate links.

:::


::: {.cell .code}
``` python
# Now, create three VMs - romeo, juliet, and router

image_uuid = os_conn.image.find_image("CC-Ubuntu20.04").id
flavor_uuid = os_conn.compute.find_flavor("m1.small").id

server_romeo = utils.ensure_server(
    os_conn,
    name="romeo_" + username,
    image_id=image_uuid,
    flavor_id=flavor_uuid,
    nics=[
        {"net-id": public_net.get("id"), "v4-fixed-ip":"192.168.10.10"},
        {"net-id": netid_1, "v4-fixed-ip":"10.10.1.100"},
    ]
)

server_juliet = utils.ensure_server(
    os_conn,
    name="juliet_" + username,
    image_id=image_uuid,
    flavor_id=flavor_uuid,
    nics=[
        {"net-id": public_net.get("id"), "v4-fixed-ip":"192.168.10.20"},
        {"net-id": netid_2, "v4-fixed-ip":"10.10.2.100"},
    ]
)

server_router = utils.ensure_server(
    os_conn,
    name="router_" + username,
    image_id=image_uuid,
    flavor_id=flavor_uuid,
    nics=[
        {"net-id": public_net.get("id"), "v4-fixed-ip":"192.168.10.30"},
        {"net-id": netid_1, "v4-fixed-ip":"10.10.1.10"},
        {"net-id": netid_2, "v4-fixed-ip":"10.10.2.10"},
    ]
)
```
:::

::: {.cell .code}
``` python
romeo_id  = chi.server.get_server('romeo_' + username).id
juliet_id = chi.server.get_server('juliet_' + username).id
router_id = chi.server.get_server('router_' + username).id
```
:::


::: {.cell .markdown}
We will wait for our VMs to come up:
:::


::: {.cell .code}
``` python
chi.server.wait_for_active(romeo_id)
chi.server.wait_for_active(juliet_id)
chi.server.wait_for_active(router_id)
```
:::

::: {.cell .markdown}
## Attach an address for SSH access
:::

::: {.cell .markdown}

Next, we will set up SSH access to the VMs.

First, we will make sure the "public" network is connected to the Internet.

:::

::: {.cell .code}
``` python
# connect them to the Internet on the "public" network (e.g. for software installation)
router = chi.network.create_router('inet-router-' + username, gw_network_name='public')
chi.network.add_subnet_to_router(router.get("id"), public_subnet.get("id"))
```
:::

::: {.cell .code}
``` python
# prepare SSH access on the three servers
fip_romeo = chi.server.associate_floating_ip(romeo_id)
fip_juliet = chi.server.associate_floating_ip(juliet_id)
fip_router = chi.server.associate_floating_ip(router_id)
```
:::

::: {.cell .markdown}
Note: The following cell assumes that a security group named "Allow SSH" already exists in your project, and is configured to allow SSH access on port 22. If you have done the "Hello, Chameleon" experiment then you already have this security group.
:::

::: {.cell .code}
``` python
[port_id_1, port_id_2, port_id_3 ] = [port['id'] for port in chi.network.list_ports() if port['port_security_enabled'] and port['network_id']==public_net.get("id")]
security_group_id = os_conn.get_security_group("Allow SSH").id
```
:::

::: {.cell .code}
``` python
%%bash -s "$PROJECT_NAME" "$security_group_id" "$port_id_1" "$port_id_2" "$port_id_3" 

export OS_PROJECT_NAME=$1
export OS_AUTH_URL=https://kvm.tacc.chameleoncloud.org:5000/v3
export OS_REGION_NAME=KVM@TACC
access_token=$(curl -s -H"authorization: token $JUPYTERHUB_API_TOKEN"     "$JUPYTERHUB_API_URL/users/$JUPYTERHUB_USER"     | jq -r .auth_state.access_token)
export OS_ACCESS_TOKEN="$access_token"

openstack port set "$3" --security-group "$2"
openstack port set "$4" --security-group "$2"
openstack port set "$5" --security-group "$2"
```
:::



::: {.cell .markdown}
Also copy your account keys to all of the resources:
:::


::: {.cell .code}
```python
remote_router = chi.ssh.Remote(fip_router) 
remote_romeo = chi.ssh.Remote(fip_romeo) 
remote_juliet = chi.ssh.Remote(fip_juliet) 
```
:::

::: {.cell .code}
``` python
nova=chi.clients.nova()
# iterate over all keypairs in this account
for kp in nova.keypairs.list(): 
    public_key = nova.keypairs.get(kp.name).public_key 
    remote_router.run(f"echo {public_key} >> ~/.ssh/authorized_keys") 
    remote_romeo.run(f"echo {public_key} >> ~/.ssh/authorized_keys") 
    remote_juliet.run(f"echo {public_key} >> ~/.ssh/authorized_keys") 
```
:::


::: {.cell .markdown}

Now, we will be able to log in to our resources over SSH! Run the following cells, and observe the output - you will see an SSH command for each of the nodes in your topology.
:::

::: {.cell .code}
``` python
# for romeo:
print(f"ssh cc@{fip_romeo}")
```
:::

::: {.cell .code}
``` python
# for juliet:
print(f"ssh cc@{fip_juliet}")
```
:::

::: {.cell .code}
``` python
# for router:
print(f"ssh cc@{fip_router}")
```
:::

::: {.cell .markdown}

Now, you can open an SSH session on any of the nodes as follows:

-   In Jupyter, from the menu bar, use File > New > Terminal to open a new terminal.
-   Copy an SSH command from the output above, and paste it into the terminal.

You can repeat this process (open several terminals) to start a session on each host and the router. Each terminal session will have a tab in the Jupyter environment, so that you can easily switch between them.

Alternatively, you can use your local terminal to log on to each host and the router, if you prefer.

:::

::: {.cell .markdown}

## Configure interfaces on the experiment network

:::


::: {.cell .markdown}

Next, we need to configure our resources - assign addresses to network interfaces, enable forwarding on the router, and install any necessary software.

:::

::: {.cell .code}
``` python
# configure the router to forward traffic
remote_router.run(f"sudo sysctl -w net.ipv4.ip_forward=1") 
remote_router.run(f"sudo ufw disable") 
remote_router.run(f"sudo apt update; sudo apt -y install net-tools") 
```
:::

::: {.cell .code}
``` python
# configure the romeo host
remote_romeo.run(f"sudo ip route add 10.10.2.0/24 via 10.10.1.10") 
remote_romeo.run(f"echo '10.10.2.100 juliet' | sudo tee -a /etc/hosts > /dev/null") 
remote_romeo.run(f"sudo apt update; sudo apt -y install iperf3") 
```
:::

::: {.cell .code}
``` python
# configure the juliet host
remote_juliet.run(f"sudo ip route add 10.10.1.0/24 via 10.10.2.10") 
remote_juliet.run(f"echo '10.10.1.100 romeo' | sudo tee -a /etc/hosts > /dev/null") 
remote_juliet.run(f"sudo apt update; sudo apt -y install iperf3") 
```
:::

::: {.cell .markdown}

## Measure the network

:::

::: {.cell .markdown}

## Emulate network impairments

:::

::: {.cell .markdown}
## Delete resources

To free your resources, run the following cell:
:::

::: {.cell .code}
``` python
for server_id in [romeo_id, juliet_id, router_id]:
    chi.server.delete_server(server_id)
    
for reserved_fip in [fip_romeo, fip_juliet, fip_router]:
    ip_details = chi.network.get_floating_ip(reserved_fip)
    chi.neutron().delete_floatingip(ip_details["id"])
    
chi.network.remove_subnet_from_router(router.get("id"), public_subnet.get("id"))
chi.network.delete_router(router.get("id"))

chi.network.delete_subnet(public_subnet.get('id'))
chi.network.delete_network(public_net.get("id"))

chi.network.delete_subnet(exp_subnet_1.get('id'))
chi.network.delete_network(exp_net_1.get("id"))

chi.network.delete_subnet(exp_subnet_2.get('id'))
chi.network.delete_network(exp_net_2.get("id"))
```
:::
