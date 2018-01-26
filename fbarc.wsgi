# Set this to fbarc viewers's virtual env
activate_this = '/opt/fbarc/ENV/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

import sys
# Set this to the path of topic tracker
sys.path.insert(0, '/opt/fbarc')

# Configure fbarc
os.environ['FBARC_INDEX']='true'
os.environ['FBARC_FILES']='/path/to/file1.jsonl,/path/to/dir'

from fbarc_viewer import app as application