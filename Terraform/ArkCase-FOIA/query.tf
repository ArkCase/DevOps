data "aws_ami" "arkcase" {
    most_recent = true
    owners      = ["self"]

    filter {
        name = "name"
        values = ["ArkCase FOIA*"]
    }
}
