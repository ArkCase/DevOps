variable "region" {
 description = "AWS region that will host our VPC"
 default = "eu-west-1"
}
variable "vpc" {
 default = "10.0.0.0/16"
}
variable "subnet_public" {
 default = "10.0.1.0/24"
}
# variable "subnet_cidrs_service" {
#  default = "10.0.1.0/24"
# }
variable "availability_zones" {
 default = "eu-west-1a"
}
