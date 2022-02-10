resource "aws_vpc" "main" {
  cidr_block = var.vpc
  enable_dns_support = "true"
  enable_dns_hostnames = "true"
  
  tags = {
    Name = "ArkCase-MP-Test"
	}
}

output "vpc_id" {
  value = "${aws_vpc.main.id}"
}