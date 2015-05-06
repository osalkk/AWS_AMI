#!/usr/bin/python

import boto.ec2
import datetime
import time
from time import mktime
import config
import logging

logger = logging.getLogger('AMIBackup')
hdlr = logging.FileHandler(config.logfile)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


signature = config.signature
retention = config.retention
ec2_region = config.region


r = boto.ec2.get_region(ec2_region)
conn = boto.connect_ec2(region=r)

reservations = conn.get_all_reservations(filters = {'tag:Backup':"daily", 'instance-state-name':'*'})

#check reservations
if ( len(reservations) == 0 ):
    logger.error( "No instance found with tag daily")
else:
    logger.info("Successfully connected to AWS")

logger.info("Script started at " + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
# loop through reservations and instances
for reservation in reservations:
    for instance in reservation.instances:
        instance_name = instance.tags['Name']
        instance_id = instance.id
        current_datetime = datetime.datetime.now()
        date_stamp = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        status = instance.update()
        states=['running','stopping','stopped']
        try:
            if status in states:
                ami_name = instance_name + signature + date_stamp
                ami_id = instance.create_image(ami_name, description="Created by script", no_reboot=True)
                logger.info("Ami " + ami_id + "creation started")
        except Exception as e:
            logger.error(e.message)

        images = conn.get_all_images(image_ids = ami_id)
        image = images[0]
        image.add_tag("Name", ami_name)

        # Deregister of Ami's
        images = conn.get_all_images(filters = {'tag:Name':instance_name + signature + '*'})

        for image in images:
            image_name = image.tags['Name']
            image_stamp = image_name.replace(instance_name + signature, "")
            image_timestamp = mktime(time.strptime(image_stamp, "%Y-%m-%d_%H-%M-%S"))
            current_timestamp = mktime(current_datetime.timetuple())
            diff_minutes = (current_timestamp - image_timestamp) / 60
            devices=image.block_device_mapping

            if ( diff_minutes > retention ):
                image.deregister()
                logger.info( image_name + " will be deleted" )
                for dev in devices:
                    snap_id=devices[dev].snapshot_id
                    b=conn.delete_snapshot(snapshot_id=snap_id)
                    logger.info(snap_id + "is deleted")

            else:
                logger.info(image_name + "will be kept")

logger.info("Script completed at " + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
