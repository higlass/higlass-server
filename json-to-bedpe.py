import sys
import json

with open(sys.argv[1], 'r') as f:
    content = json.load(f)

with open('bed2.bedpe', 'w') as f:
    f.write('chr1\tstart1\tend1\tchr2\tstart2\tend2\n')
    for i, line in enumerate(content):
        line = ['chr{}'.format(line[0]), line[1] - 10000, line[2] + 10000, 'chr{}'.format(line[4]), line[5] - 10000, line[6] + 10000]
        line = [str(ass) for ass in line]
        f.write('\t'.join(line) + '\n')
