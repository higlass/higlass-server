#!/bin/sh
#source activate snakes
wget $1
/home/ubuntu/miniconda2/envs/snakes/bin/python recursive_agg_onefile.py $1
mv *.cool ./data
#source deactivate snakes
