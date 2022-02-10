data "terraform_remote_state" "main" {
  backend = "local"
config = {
    path = "../terraform-vpc/terraform.tfstate"
    }
}

resource "aws_instance" "web" {

    ami = "${data.aws_ami.arkcase.id}"
    instance_type = "t3.xlarge"
    # key_name = "foia-hud-arkcase-demo"

    # VPC
    subnet_id = "${data.terraform_remote_state.main.outputs.subnet_id}"

    # Security Group
    vpc_security_group_ids = [ "${data.terraform_remote_state.main.outputs.sg_id}" ]
}
