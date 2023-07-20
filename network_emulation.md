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
```
:::

::: {.cell .markdown}

We indicate that we’re going to use the KVM@TACC site. We also need to specify the name of the Chameleon "project: that this experiment is part of. The project name will have the format “CHI-XXXXXX”, where the last part is a 6-digit number, and you can find it on your [user dashboard](https://chameleoncloud.org/user/dashboard/).

In the cell below, replace the project ID with your own project ID, then run the cell.

:::


::: {.cell .code}
```python
chi.use_site("KVM@TACC")
PROJECT_NAME = "CHI-XXXXXX"
chi.set("project_name", PROJECT_NAME)

# configure openstacksdk for actions unsupported by python-chi
os_conn = chi.clients.connection()
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
netid_1 = exp_net_1['id']
netid_2 = exp_net_2['id']
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

At this point, we should be able to log in to our resources over SSH! Run the following cells, and observe the output - you will see an SSH command for each of the nodes in your topology.
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

Next, we are going to measure the characteristics of the existing network - 

* what data rate do we observe when we try to send data as fast as possible through the network?
* how much delay is there, and how much delay variation, when we send small `ping` messages across the network and measure the time to receive a response?
:::


::: {.cell .markdown}

We will use the `iperf3` command to send data from "romeo" to "juliet" and measure the data rate. First, we'll set up "juliet" to *receive* one data flow. Then, we'll ask "romeo" to send a data flow for ten seconds, and report back with an average data rate.

:::


::: {.cell .code}
```python
remote_juliet.run('iperf3 -s -1', disown=True)
```
:::

::: {.cell .code}
```python
remote_romeo.run('iperf3 -c juliet')
```
:::

::: {.cell .markdown}

Next, we will use the `ping` command to send those `ping` messages (10 of them!) and responses from "romeo" to "juliet". The output will include the round trip time of each of the ten messages, and at the end, the minimum, average, maximum, and variation of the delay.

:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 10 juliet')
```
:::

::: {.cell .markdown}

## Emulate network impairments

:::


::: {.cell .markdown}

Now that we understand the characteristics of the "real" network, we can add network *impairments* that make it mimic other, *worse* networks.

Note the word "impairment" - we can make the network *worse* but there is nothing we can do to make it better!

For example, if the "real" network is capable of transferring data at 2 Gbps, we can *slow it down* and make it transfer data at only 100 Mbps. But we can't make it *faster*, so we won't be able to make it work at 10 Gbps.

Similarly, if the delay across the "real" networks is about 1 ms, we can *add* 20 ms of delay to make the overall delay about 20 ms, but we can't make the delay be *less* than 1 ms.

:::


::: {.cell .markdown}

To add network impairments, we will use the Linux traffic control system, `tc`, which can apply various "rules" to all packets *leaving* a network interface. We will apply these rules at the router, since all traffic between "romeo" and "juliet" goes through the router. 

* To add additional delay and delay variation to the *round trip time* between "romeo" and "juliet", we would use `netem` and put *half* of the additional delay on the router interface that is on the same network link as "juliet" (this will apply to data from "romeo" to "juliet"), and the other *half* on the router interface that is on the same network link as "romeo" (this will apply to data from "juliet" to "romeo"). The *round trip delay* is the sum of the delays in each direction.
* To apply random packet loss to the data going from "romeo" *to* "juliet", we would use `netem` to add loss at the router interface that is on the same network link as "juliet", since packets going to "juliet" are going to *leave* the router through this interface.
* To slow down the data rate for data going from "romeo" *to*" "juliet", we would apply a *token bucket* filter at the router interface that is on the same network link as "juliet", since packets going to "juliet" are going to *leave* the router through this interface.

We'll start by adding these impairments individually, and then we will see how to add these in combination.

:::


::: {.cell .markdown}
One important note before we begin: in the commands that follow, we want to apply an impairment to a specific network interface on the router, and we need to refer to the interface by name. The router has multiple network interfaces, two of which are the "experiment" interfaces that we want to modify - we can see them by running `ip addr` on the router:
:::


::: {.cell .code}
```python
remote_router.run('ip addr')
```
:::


::: {.cell .markdown}
We don't know in advance what the interfaces will be named - e.g. in this experiment, the interface that connects the router to the link with "juliet" may be named `ens8` but in the next experiment it could be named `ens4`! But, in the commands that follow, we need to name the interface.

Therefore, instead of using an interface name directly in these commands, we will use a command that returns the name of a particular interface. For example, the command
:::

::: {.cell .code}
```python
remote_router.run('ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+"')
```
:::


::: {.cell .markdown}
will return the name of the router interface that will be used to forward packets to "juliet" (10.10.2.100), and the command
:::

::: {.cell .code}
```python
remote_router.run('ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+"')
```
:::


::: {.cell .markdown}
will return the name of the router interface that will be used to forward packets to "romeo" (10.10.1.100). When we use these commands inside a `$()` within another command, the command inside the `$()` is executed and its value is returned and used in the "parent" command. This way, we can specify an interface name in the `tc` commands without even knowing what the interface name is!
:::


::: {.cell .markdown}
With that in mind, let's start by deleting any `tc` elements that might already be set up on either of the router interfaces. We specify that we want to delete (`del`) whatever might be there, we specify the name of the network interface (`dev` followed by a command inside `$()` which will be replaced by an interface name!), and we specify that we want to delete everything from the `root` of the interface (in case there is a "chain" of elements applied there!)

If there is no `tc` element already applied, then trying to delete it will return an error, but that's OK!
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::

::: {.cell .markdown}
Now, let's use `netem` to add 10 ms of delay in *each* direction, for a total of 20 ms added to the round trip time. 

On the router, we will run:
:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms')
```
:::



::: {.cell .markdown}
To test the change in delay, we will run our `ping` test again, but we'll make it a little bit longer this time:
:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 60 juliet')
```
:::

::: {.cell .markdown}

Validate that the results now show an additional 20 ms of delay in the round trip time.

:::


::: {.cell .markdown}
Instead of adding a constant delay (same delay applied to every packet), we may want to add delay with some *variation*. Let's *replace* the previous `netem` element with a different one, that also specifies a delay variation (second value after the word `delay`):

:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc replace dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms 5ms')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc replace dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms 5ms')
```
:::

::: {.cell .markdown}

Validate that the round trip time reported by `ping` now has substantially more variation:

:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 60 juliet')
```
:::


::: {.cell .markdown}
The `netem` element can also be used to add packet loss. Most networks have very little packet loss, but for this example, we'll make it more extreme - we'll specify 10% packet loss, which means that 1 out of every 10 packets will be dropped (on average). We will *only* apply this to packets going from "romeo" to "juliet", not for packets going in the other direction.

First, we'll delete the existing (delay) `netem` elements, then we'll add one that emulates packet loss:
:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root netem loss 10%')
```
:::

::: {.cell .markdown}

Validate that the `ping` results now show packet loss:

:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 60 juliet')
```
:::

::: {.cell .markdown}
We can specify both `delay` and `loss` together in a `netem`. For example, if we want to delete any existing `tc` elements and then add:

* 10ms delay with 5ms variation and 10% packet loss to packets from "romeo" to "juliet"
* and 10ms delay with 5ms variation to packets from "juliet" to "romeo"

we could do:
:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root')
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms 5ms')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root')
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms 5ms loss 10%')
```
:::


::: {.cell .markdown}

Validate that the `ping` results now show the added delay *and* the packet loss:

:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 60 juliet')
```
:::


::: {.cell .markdown}

To slow down the data rate of the network, we prefer to use a different `tc` element, named `htb`. Let's delete our `netem` element, and then try to add an `htb` that limits the rate of the data transfer from "romeo" to "juliet" to 100 Mbps. As packets arrive at the router, they will wait in a queue (in the order in which they arrived, so FIFO - first in, first out), and they will be released only at a rate of 100 Mbps. Also, the queue size will be limited to 0.5 MByte, so once packets arrive at the queue and find it to be full, they will be dropped. This will indicate to the sender ("romeo") that it should slow down its sending rate.

:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::


::: {.cell .code}
```python
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root handle 1: htb default 3')
remote_router.run('sudo tc class add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") parent 1: classid 1:3 htb rate 100Mbit')
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") parent 1:3 handle 3: bfifo limit 0.5MByte')

```
:::


::: {.cell .markdown}

We will validate the change using `iperf3` to generate a data flow from "romeo" to "juliet" -

:::



::: {.cell .code}
```python
remote_juliet.run('iperf3 -s -1', disown=True)
```
:::

::: {.cell .code}
```python
remote_romeo.run('iperf3 -c juliet')
```
:::


::: {.cell .markdown}

Finally, we can also add a `netem` element *after* an `htb` token bucket, to combine rate limiting along with delay (and/or packet loss)! Try the following sequence of commands:

:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::

::: {.cell .code}
```python
remote_router.run('sudo tc qdisc del dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root')
```
:::


::: {.cell .code}
```python
# only add delay to the direction from "juliet" toward "romeo"
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.1.100 | grep -oP "(?<=dev )[^ ]+") root netem delay 10ms')
```
:::


::: {.cell .code}
```python
# add delay and also rate limiting in the direction from "romeo" toward "juliet"
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") root handle 1: htb default 3')
remote_router.run('sudo tc class add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") parent 1: classid 1:3 htb rate 100Mbit')
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") parent 1:3 handle 3: netem delay 10ms')
remote_router.run('sudo tc qdisc add dev $(ip route get 10.10.2.100 | grep -oP "(?<=dev )[^ ]+") parent 3: bfifo limit 0.5MByte')
```
:::


::: {.cell .markdown}
and, validate the change:
:::


::: {.cell .code}
```python
remote_juliet.run('iperf3 -s -1', disown=True)
```
:::

::: {.cell .code}
```python
remote_romeo.run('iperf3 -c juliet')
```
:::

::: {.cell .code}
```python
remote_romeo.run('ping -c 60 juliet')
```
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
