"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws

# Dynamically query the Amazon Linux machine image
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["137112412989"],
    filters=[{"name":"name",
            "values":["amzn-ami-hvm-*-x86_64-ebs"]
            }
            ]
)

# Get Virtual Private Cloud
vpc = aws.ec2.get_vpc(default=True)

# Setup AWS security group
group = aws.ec2.SecurityGroup(
    "web-secgrp",
    description='Enable HTTP access',
    vpc_id=vpc.id,
    ingress=[
        { 'protocol': 'icmp', 'from_port': 8, 'to_port': 0, 'cidr_blocks': ['0.0.0.0/0'] },
        { 'protocol': 'tcp', 'from_port': 80, 'to_port': 80, 'cidr_blocks': ['0.0.0.0/0'] }
    ],
    # Add egress rule for load balancer
    egress=[
        { 'protocol': 'tcp', 'from_port': 80, 'to_port': 80, 'cidr_blocks': ['0.0.0.0/0'] },
    ]
)


# Create load balancer
vpc_subnets = aws.ec2.get_subnet_ids(vpc_id=vpc.id)

lb = aws.lb.LoadBalancer(
    "loadbalancer",
    internal=False,
    security_groups=[group.id],
    subnets=vpc_subnets.ids,
    load_balancer_type="application",
)

target_group = aws.lb.TargetGroup(
    "target-group", port=80, protocol="HTTP", target_type="ip", vpc_id=vpc.id
)

listener = aws.lb.Listener(
    "listener",
    load_balancer_arn=lb.arn,
    port=80,
    default_actions=[{"type": "forward", "target_group_arn": target_group.arn}],
)


ips = []
hostnames = []

# Create servers for each availability zone in your AWS region
for az in aws.get_availability_zones().names:
    server = aws.ec2.Instance(
        f'web-server-{az}',
        instance_type="t2.micro",
        security_groups=[group.name],
        ami=ami.id,
        availability_zone=az,
        # Spins up simple Python webserver
        user_data="""
        #!/bin/bash
        echo \"Hello, World! -- from {}\" > index.html
        nohup python -m SimpleHTTPServer 80 &  
        """.format(az),
        tags={
            "Name": "web-server",
        },
    )

    # populate the ips and hostnames lists
    ips.append(server.public_ip)
    hostnames.append(server.public_dns)

    attachment = aws.lb.TargetGroupAttachment(f"web-server-{az}",
                                                target_group_arn=target_group.arn,
                                                target_id=server.private_ip,
                                                port=80)

# Export EC2 instances' resulting IP address and hostname
pulumi.export('ip', ips)
pulumi.export('hostname', hostnames)
pulumi.export("url", lb.dns_name)
