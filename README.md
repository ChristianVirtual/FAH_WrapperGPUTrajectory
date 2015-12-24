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

![FAH GPU trajectory](ttp://imageshack.com/a/img905/7480/JObdT1.png)

Attention: right now not much more then a proof-of-concept ... still some work to be done ...
