import fileinput
import json
from collections import Counter
import sys

"""
Counts the node types provided in a list of JSON files or stdin.
"""

if __name__ == '__main__':
    stats_counter = Counter()

    for line in fileinput.input():
        node = json.loads(line)
        if 'id' in node:
            if 'metadata' in node:
                stats_counter[node['metadata']['type']] += 1
        else:
            print('Error line: {}'.format(line))
            sys.exit(1)

    total = 0
    for node_type, count in stats_counter.most_common():
        total += count
        print('{}: {:,}'.format(node_type, count))
    print('Total: {:,}'.format(total))