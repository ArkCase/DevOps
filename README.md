ArkCase DevOps stuff
====================

How do the CloudFormation templates work?
-----------------------------------------

In order to create/update a CloudFormation stack, the CloudFormation
templates and their dependencies must be published first. This is
achieved by running the following command:

    $ AWS_PROFILE=myprofile ./publish.sh

Once this is done, anyone can create an ArkCase stack by using a
public `arkcase.yml` template file, for example:

    https://arkcase-public-us-east-1.s3.amazonaws.com/DevOps/YYYYMMDD-HHMM/CloudFormation/arkcase.yml

