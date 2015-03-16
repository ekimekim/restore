
import gevent.monkey
gevent.monkey.patch_all()

from restore.tool import cli

cli()
