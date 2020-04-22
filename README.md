ArkCase DevOps stuff
====================

How do the CloudFormation templates work?
-----------------------------------------

In order to create/update a CloudFormation stack, the CloudFormation
templates and their dependencies must be published first. This is
achieved by running the following command:

    $ AWS_PROFILE=myprofile ./publish.py DEV

For usage, run:

    $ ./publish.py -h

Once this is done, you can create an ArkCase stack by using the
[CloudFormation/arkcase.yml](CloudFormation/arkcase.yml) template.

Alternatively, anyone can create an ArkCase stack by using the public
`arkcase.yml` template file, for example:

    https://arkcase-public-us-east-1.s3.amazonaws.com/DevOps/ACM-TAG-YYYYMMDD-HHMM/CloudFormation/arkcase.yml

