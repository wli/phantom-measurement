import glob
import subprocess
import tempfile

PHANTOMJS_PATH = 'phantomjs'

# Build JS file
out = tempfile.NamedTemporaryFile(suffix='.js')
for fn in glob.glob('modules/*.js'):
  f = open(fn, 'r')
  out.write(f.read())
  out.write('\n')

out.write(open('base.js', 'r').read())
out.flush()
print out.name


# Run JS file
phantom = subprocess.Popen([PHANTOMJS_PATH, '--load-images=no', out.name, 'http://www.nytimes.com'])
phantom.wait()

# Process output

# Delete temporary JS file
out.close()

