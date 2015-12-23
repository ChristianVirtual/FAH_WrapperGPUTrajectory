# FAH_WrapperGPUTrajectory

Please modify the source file with the hostnames

1. where the wrapper is running
2. where the FAHClient is running

Those both hostnames for the time beeing need to be the same !

start the script with
```python FAH_WrapperGPUTrajectory.py```


Then on a remote machine (or the same) start the viewer

```FAHViewer --connect=\<wrapper_hostname\>:36331 --password=\<password\> --slot=1```

As result something like this should appear:
![FAH GPU trajectory](http://imageshack.us/a/img910/339/w1sh5j.jpg)

Attention: right now not much more then a proof-of-concept ... still too many hardcoded assumptions like the working folder (always workunit 01); some effort to make it end-user-friendly to be done
