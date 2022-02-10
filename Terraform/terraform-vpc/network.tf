resource "aws_internet_gateway" "Armedia-GW" {
  vpc_id = aws_vpc.main.id
  tags = {
    Name = "armedia-gw"
	}
}

resource "aws_route_table" "public-rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
	gateway_id = aws_internet_gateway.Armedia-GW.id
	}
  tags = {
    Name = "Armedia-RT"
	}
}

resource "aws_security_group" "ssh-allowed" {

    vpc_id = "${aws_vpc.main.id}"

    egress {
        from_port = 0
        to_port = 0
        protocol = -1
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        
        // This means, all ip address are allowed to ssh !
        // Do not do it in the production. Put your office or home address in it!
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        from_port = 443
        to_port = 443
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

output "sg_id" {
  value = "${aws_security_group.ssh-allowed.id}"
}