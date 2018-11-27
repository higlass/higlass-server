import sys

with open(sys.argv[1], 'r') as f:
    content = f.readlines()

with open('bed.bedpe', 'w') as f:
    f.write('chr1\tstart1\tend1\tchr2\tstart2\tend2\n')
    for i, line in enumerate(content):
        line = line.strip()
        if i > 1:
            bedA = content[i - 1].split('\t')
            bedB = line.split('\t')
            bedpe = [bedA[0], bedA[1], bedA[2], bedB[0], bedB[1], bedB[2]]
            f.write('\t'.join(bedpe) + '\n')
