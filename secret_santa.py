import yaml
import argparse
import random
import time
import sys
import boto3


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


class Person:
    def __init__(self, name, phone, invalid_matches):
        self.name = name
        self.phone = phone
        self.invalid_matches = invalid_matches

    def __str__(self):
        return "%s <%s>" % (self.name, self.email)


class Pair:
    def __init__(self, giver, reciever):
        self.giver = giver
        self.reciever = reciever

    def __str__(self):
        return "%s ---> %s" % (self.giver.name, self.reciever.name)


def parse_yaml(yaml_path):
    return yaml.load(open(yaml_path))


def verify_config(config):
    required = (
        'PARTICIPANTS',
        'MESSAGE',
    )
    for key in required:
        if key not in config.keys():
            raise Exception(
                'Required parameter %s not in yaml config file!' % (key,))

    if len(config['PARTICIPANTS']) < 2:
        raise Exception('Not enough participants found in config.')


def choose_reciever(giver, recievers):
    choice = random.choice(recievers)
    if choice.name in giver.invalid_matches or giver.name == choice.name:
        if len(recievers) is 1:
            raise Exception('Only one reciever left, try again')
        return choose_reciever(giver, recievers)
    else:
        return choice


def create_pairs(g, r):
    givers = g[:]
    recievers = r[:]
    pairs = []
    for giver in givers:
        try:
            reciever = choose_reciever(giver, recievers)
            recievers.remove(reciever)
            pairs.append(Pair(giver, reciever))
        except:
            return create_pairs(g, r)
    return pairs


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def main(argv=None):
    args = parse_args()
    send = args['send']

    config = parse_yaml(args['config_file'])
    verify_config(config)

    participants = config['PARTICIPANTS']
    givers = []
    for person in participants:
        person = Person(person['name'], person['phone'], person['dont_pair'])
        givers.append(person)

    recievers = givers[:]
    pairs = create_pairs(givers, recievers)
    if not send:
        print """
Test pairings:

%s

To send out emails with new pairings,
call with the --send argument:

    $ python secret_santa.py --send

            """ % ("\n".join([str(p) for p in pairs]))

    if send:
        session = boto3.session.Session(
            profile_name=args['aws_profile'],
            region_name=args['aws_region']
            )
        client_sns = session.client('sns')
    for pair in pairs:
        body = (config['MESSAGE']).format(
                santa=pair.giver.name,
                santee=pair.reciever.name,
                )
        if send:
            response = client_sns.publish(
                PhoneNumber=pair.giver.phone,
                Message=body
            )
            print "SMS messaged %s <%s>" % (pair.giver.name, pair.giver.phone)
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
