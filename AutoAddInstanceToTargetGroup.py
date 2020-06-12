import json
import boto3
import datetime

def lambda_handler(event, context):
    
    TARGET_GROUP_ARN_DICTIONARY = {

    'consumer-prod-': 'TARGET_GROUP_ARN_GOES_HERE',
    'API-prod-': 'TARGET_GROUP_ARN_GOES_HERE'

    }
    
    def GetEnvironmentName(ag_group_name):
        client = boto3.client('autoscaling')
        response = client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[
            ag_group_name,
        ])
    
        response = response['AutoScalingGroups']
        print(response)
        for data in response:
           tags= data['Tags'][0]
    
        print(tags)
    
        if tags['Key'] == 'AppName' and tags['Value'] == 'API-prod':
            print("This is API-Prod")
            Name = tags['Value']
            Name = Name + '-'
        elif tags['Key'] == 'AppName' and tags['Value'] == 'Consumer-prod':
            print("This is Consumer-Prod")
            Name = tags['Value']
            Name = Name.lower() + '-'
        else:
            print("This application is not required..Exiting.")
            quit()
    
        return Name
    
    def GetEnvironmentBeanstalkName(ag_group_name):
        client = boto3.client('autoscaling')
        response = client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[
            ag_group_name,
        ])
    
        response = response['AutoScalingGroups']
        print(response)
        
        for data in response:
            for tag in data['Tags']:
                if tag['Key'] == 'elasticbeanstalk:environment-name':
                    return tag['Value']
    
        print("Unable to determine beanstalk name..Exiting.")
        quit()
    

    # Retrieves the name of the current Consumer-Prod Environment
    def CheckEnvironment(NAME):
        client = boto3.client('elasticbeanstalk',region_name='us-west-2')
        response = client.describe_environments()
        
        # Get Environments
        envs = response['Environments']
    
        for env in envs:
            
            if env['EnvironmentName'] == 'Worker':
                continue
            
            env_name = env['EnvironmentName']
            env_dns = env['CNAME']
            
            if NAME in env_name:
                env_health_response = client.describe_environment_health(EnvironmentName = env_name, AttributeNames=['All'])
                
                request_count = env_health_response['ApplicationMetrics']['RequestCount']
                print("This is the request_count:")
                print(request_count)
                print("This is the CNAME:")
                print(env_dns)
                
                if (env_dns == "CONSUMER_BEANSTALK_DNS_GOES_HERE" or env_dns == "API_BEANSTALK_DNS_GOES_HERE"):
                    return env_name
                    
        raise Exception('No Suitable Environment Found')


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
                return True
    
    
    
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
        sns_message = boto3.client('sns')
    
        for instance in missing_instances:
            print("Registering instance: " + instance)
            response = client.register_targets(TargetGroupArn=TARGET_GROUP_ARN, Targets=[{'Id': instance}])
            
            sns_response = sns_message.publish(
                TopicArn='arn:aws:sns:us-west-2:172136542978:SystemAlerts',
                Message='The following instance is being added to the target group: ' + instance,
                Subject='ALERT - Consumer-Prod Scaling'
            )
        print(sns_response)
    
    # Program Start
    
    print("This is the event object")
    print(event)
    
    print('Getting Autoscaling Group Name from the Event Object...')
    ag_group_name = event['resources'][0].split("/").pop()
    print('This is the Auto-scaling group name ' + ag_group_name)
    
    BEANSTALK_NAME = GetEnvironmentBeanstalkName(ag_group_name)
    print('Beanstalk of this event is: ' + BEANSTALK_NAME);
    
    NAME = GetEnvironmentName(ag_group_name)
    TARGET_GROUP_ARN = TARGET_GROUP_ARN_DICTIONARY[NAME]
    
    env_name = CheckEnvironment(NAME)
    if env_name != BEANSTALK_NAME:
        print("Failed to get valid environment name..Exiting.")
        quit()
        
    tag = GetNeededTag(env_name)
    
    if tag == True:
        autoscaling_group_name = ag_group_name
        autoscaling_instance_ids = GetAutoScalingInstanceIDs(autoscaling_group_name)
        target_group_ids = GetTargetGroupIds(TARGET_GROUP_ARN)
    
        print("These are the Instances in the AutoScaling Group: " + autoscaling_group_name)
        print(autoscaling_instance_ids)
        print("These are the Instances in the Target Group:")
        print(target_group_ids)
        missing_instances = GetMissingInstances(autoscaling_instance_ids,target_group_ids)
        print("These are the Missing Instances in the Target Group:")
        print(missing_instances)
    
        # If the array of missing instances is empty, end the program. Otherwise, call the Register Function
        if not missing_instances:
            print ("There are no instances to add.")
        else:
            RegisterInstancesToTargetGroup(missing_instances,TARGET_GROUP_ARN)
    else:
        print("There is nothing to do.")
    
