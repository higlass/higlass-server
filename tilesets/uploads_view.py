from __future__ import print_function

import boto3
import hashlib

import resgen_server.settings as hss

import json
import logging
import numpy as np
import os.path as op

import tilesets.models as tm

try:
    import cPickle as pickle
except:
    import pickle
import slugid

from rest_framework.authentication import BasicAuthentication,TokenAuthentication
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

@api_view(['GET'])
@authentication_classes((BasicAuthentication,))
def prepare_file_upload(request):
    '''
    Retrieve a list of locations and return the corresponding matrix fragments

    Args:

    request (django.http.HTTPRequest): The request object containing the
        list of loci.

    Return:

    '''
    bucket=hss.AWS_BUCKET

    file_directory = slugid.nice().decode('utf8')
    key="{}/{}".format(hss.AWS_BUCKET_FILE_PREFIX, file_directory);

    policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': ['s3:PutObject', 's3:ListBucket'],
                    'Resource': 'arn:aws:s3:::{bucket}/{key}/*'.format(bucket=bucket, key=key),
                    },
                ]
            }

    client = boto3.client('sts',
            aws_access_key_id=hss.AWS_ACCESS_KEY,
            aws_secret_access_key=hss.AWS_SECRET_KEY,
            )

    response = client.get_federation_token(Name="bob", Policy=json.dumps(policy))
    creds = {
                'accessKeyId': response['Credentials']['AccessKeyId'],
                'secretAccessKey': response['Credentials']['SecretAccessKey'],
                'sessionToken': response['Credentials']['SessionToken'],
                'uploadBucket': bucket,
                'uploadBucketPrefix': key,
                'fileDirectory': file_directory
            }

    return JsonResponse(creds)


@api_view(['POST'])
@authentication_classes((BasicAuthentication,))
def finish_file_upload(request):
    '''
    A file has been uploaded to S3. Finish the upload here by adding the file
    to the database.

    The request should contain the location that file was uploaded to.

    Parameters:
        request: The HTTP request associated with this POST action

    Returns:
        JsonResponse: A response containing the uuid of the newly added tileset
    '''
    body = json.loads(request.body.decode('utf8'))
    print("request:", request)

    media_base_path = op.realpath(hss.MEDIA_ROOT)
    aws_base_path = op.join(hss.MEDIA_ROOT, hss.AWS_BUCKET_MOUNT_POINT)

    data_root = op.realpath(aws_base_path)
    abs_filepath = op.realpath(op.join(aws_base_path, body['filepath']))

    if abs_filepath.find(data_root) != 0:
        # check ot make sure that the filename is contained in the AWS_BUCKET_MOUNT
        # e.g. that somebody isn't surreptitiously trying to pass in ('../../file')
        return JsonRespnose({'error': "Provided path ({}) not in the data path".format(body['filepath'])}, status=500)
    else:
        if not op.exists(abs_filepath):
            return JsonResponse({'error': "Specified file ({}) does not exist".format(body['filepath'])}, status=500)

    baked_filepath = abs_filepath
    diff_path=abs_filepath[len(media_base_path)+1:]    #+1 for the slash

    print("user:", request.user);
    obj = tm.Tileset.objects.create(
            datafile=diff_path,
            name=op.basename(body['filepath']),
            owner=request.user)

    return JsonResponse({'uuid': obj.uuid.decode('utf8')})
