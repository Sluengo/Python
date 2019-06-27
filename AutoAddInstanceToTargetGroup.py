import boto3

# Variable list
NAME = 'consumer-prod'
TARGET_GROUP_ARN = 'arn:aws:elasticloadbalancing:us-west-2:172136542978:targetgroup/puppyspot-targets-core-prod/cc8f9632739f7370'



# Retrieves the name of the current Consumer-Prod Environment
def GetEnvName(NAME):
    client = boto3.client('elasticbeanstalk',region_name='us-west-2')
    response = client.describe_environments()
    print(response)
    # Get Environments
    envs = response['Environments']

    for env in envs:
        env_names = env['EnvironmentName']
        if NAME in env_names:
            env_name = env['EnvironmentName']

    return env_name


# Retrieves the required Tag for the program to continue
def GetNeededTag(env_name):
    client = boto3.client('elasticbeanstalk',region_name='us-west-2')
    response = client.describe_environments(EnvironmentNames=[env_name])
    env_details = response['Environments']

    for env in env_details:
        env_arn = env['EnvironmentArn']

    tags = client.list_tags_for_resource(ResourceArn=env_arn)

    for tag in tags['ResourceTags']:
        if tag['Key'] == 'AutoAdd TargetGroup':
            print("This is consumer prod")
            return True


# Retrieves the name of the Autoscaling Group attached to the Environment
def GetAutoScalingGroupName(env_name):
    client = boto3.client('elasticbeanstalk',region_name='us-west-2')
    env_resources = client.describe_environment_resources(EnvironmentName=env_name)
    env_resources = env_resources['EnvironmentResources']

    for autoscaling_name in env_resources['AutoScalingGroups']:
        autoscaling_group_name = autoscaling_name['Name']

    return autoscaling_group_name

# Retrieves a list of AutoScaling Group IDs (from Elastic Beanstalk)
def GetAutoScalingInstanceIDs(autoscaling_group_name):
    autoscaling_instance_ids = []
    client = boto3.client('autoscaling')
    autoscaling_instance_config = client.describe_auto_scaling_groups(AutoScalingGroupNames=[autoscaling_group_name])
    autoscaling_instance_config  = autoscaling_instance_config ['AutoScalingGroups']
    for config in autoscaling_instance_config:
        autoscaling_instances = config['Instances']

    for instance in autoscaling_instances:
        autoscaling_instance_ids.append(instance['InstanceId'])

    return autoscaling_instance_ids

# Retrieves a list of Target Group IDs
def GetTargetGroupIds(TARGET_GROUP_ARN):
    target_group_ids = []
    client = boto3.client('elbv2')
    target_group_config = client.describe_target_health(TargetGroupArn = TARGET_GROUP_ARN)
    target_group_config = target_group_config['TargetHealthDescriptions']

    for config in target_group_config:
        target_group_ids.append(config['Target']['Id'])

    return target_group_ids

# Compares the list of instances in the autoscaling group against the instances in the target group. If there are
# missing instances, it will append them to the missing_instances list.
def GetMissingInstances(autoscaling_instance_ids,target_group_ids):
    missing_instances = []

    for instance in autoscaling_instance_ids:
        if not instance in target_group_ids:
            missing_instances.append(instance)

    return missing_instances

# Registers the missing instances in the autoscaling group to the target group
def RegisterInstancesToTargetGroup(missing_instances,TARGET_GROUP_ARN):
    client = boto3.client('elbv2')

    for instance in missing_instances:
        response = client.register_targets(TargetGroupArn=TARGET_GROUP_ARN, Targets=[{'Id': instance}])

# Program Start

env_name = GetEnvName(NAME)
tag = GetNeededTag(env_name)

if tag == True:
    autoscaling_group_name = GetAutoScalingGroupName(env_name)
    autoscaling_instance_ids = GetAutoScalingInstanceIDs(autoscaling_group_name)
    target_group_ids = GetTargetGroupIds(TARGET_GROUP_ARN)

    print("These are the Instances in the AutoScaling Group: " + autoscaling_group_name)
    print(autoscaling_instance_ids)
    print("These are the Instances in the Target Group")
    print(target_group_ids)
    missing_instances = GetMissingInstances(autoscaling_instance_ids,target_group_ids)
    print("These are the Missing Instances in the Target Group")
    print(missing_instances)

    # If the array of missing instances is empty, end the program. Otherwise, call the Register Function
    if not missing_instances:
        print ("There are no instances to add.")
    else:
        RegisterInstancesToTargetGroup(missing_instances,TARGET_GROUP_ARN)
else:
    print("There is nothing to do.")




