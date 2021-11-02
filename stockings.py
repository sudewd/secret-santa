import argparse
import random
import boto3
import time
import sys
import yaml
import logging

logger = logging.getLogger(__name__)

def parse_args():
    '''Command Line Arguments for Program'''
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--send',
                        action='store_true',
                        dest='send',
                        default=False,
                        required=False,
                        help='Send Secret Santas SMS message of recipent.')
    parser.add_argument('-p', '--aws-profile',
                        action='store',
                        dest='aws_profile',
                        default='default',
                        required=False,
                        help='Use a specific AWS profile from your credential file.')
    parser.add_argument('-r', '--aws-region',
                        action='store',
                        dest='aws_region',
                        default='us-west-2',
                        required=False,
                        help='Use a specific AWS region to publish SMS messages to.')
    parser.add_argument('-c', '--config',
                        action='store',
                        dest='config_file',
                        default='config.yaml',
                        required=False,
                        help='Use a specific config file. Default: config.yaml')
    args = vars(parser.parse_args())
    return args

def parse_yaml(yaml_path):
    return yaml.safe_load(open(yaml_path))

def verify_config(config):
    required = (
        'PARTICIPANTS',
        'MESSAGE',
    )
    for key in required:
        if key not in config.keys():
            raise Exception(
                'Required parameter {key} not in yaml config file!')

    if len(config['PARTICIPANTS']) < 2:
        raise Exception('Not enough participants found in config.')


class Person:
    def __init__(self, name, phone, invalid_matches):
        self.name = name
        self.phone = phone
        self.invalid_matches = invalid_matches
        self.category = ''

    def __str__(self):
        return "{} <{}> - {}".format(self.name, self.phone, self.category)

def get_category(giver, categories):
    category = random.choice(categories)
    if category in giver.invalid_matches:
        if len(categories) == 1:
            raise Exception('Only one reciever left, try again')
        return get_category(giver, categories)
    else:
        return category

def create_pairs(g, c):
    givers = g[:]
    categories = c[:]
    pairs = []
    for giver in givers:
        try: 
            giver.category = get_category(giver, categories)
            categories.remove(giver.category)
            pairs.append(giver)
        except:
            return create_pairs(g, c)
    return pairs

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

class SnsWrapper:
    """Encapsulates Amazon SNS topic and subscription functions."""
    def __init__(self, sns_resource):
        """
        :param sns_resource: A Boto3 Amazon SNS resource.
        """
        self.sns_resource = sns_resource

    def publish_text_message(self, phone_number, message):
        """
        Publishes a text message directly to a phone number without need for a
        subscription.

        :param phone_number: The phone number that receives the message. This must be
                             in E.164 format. For example, a United States phone
                             number might be +12065550101.
        :param message: The message to send.
        :return: The ID of the message.
        """
        try:
            response = self.sns_resource.meta.client.publish(
                PhoneNumber=phone_number, Message=message)
            message_id = response['MessageId']
            logger.info("Published message to %s.", phone_number)
        except ClientError:
            logger.exception("Couldn't publish message to %s.", phone_number)
            raise
        else:
            return message_id

def main(argv=None):
    args = parse_args()
    send = args['send']

    config = parse_yaml(args['config_file'])
    verify_config(config)

    participants = config['PARTICIPANTS']
    categories = config['CATEGORIES']
    givers = []
    for person in participants:
        person = Person(person['name'], person['phone'], person['dont_pair'])
        givers.append(person)

    # recievers = givers[:]
    pairs = create_pairs(givers, categories)
    if not send:
        print("""
Test pairings:

{}

To send out emails with new pairings,
call with the --send argument:

    $ python secret_santa.py --send
            """.format("\n".join([str(p) for p in pairs])))

    if send:
        sns_wrapper = SnsWrapper(boto3.resource('sns'))
    for p in pairs:
        body = (config['MESSAGE']).format(
                p.name, p.category
                )
        if send:
            sns_wrapper.publish_text_message(p.phone, body)
            print("SMS messaged {} {} - something {}".format(p.name, p.phone, p.category))
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
