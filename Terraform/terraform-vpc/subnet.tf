resource "aws_subnet" "subnet-public" {
  vpc_id = aws_vpc.main.id
  cidr_block = "${var.subnet_public}"
  availability_zone = var.availability_zones
  map_public_ip_on_launch = true
  tags = {
    Name = "Marketplace subnet"
	}
}

output "subnet_id" {
  value = "${aws_subnet.subnet-public.id}"
}