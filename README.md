# FAH_WrapperGPUTrajectory

With new version 2.0 the hostname will be determined from the socket interface via gethostname(); in case of trouble you still can define the hostnames in the source (but should not be needed)

~~Please modify the source file with the hostnames~~

~~1. where the wrapper is running~~
~~2. where the FAHClient is running~~

~~Those both hostnames for the time beeing need to be the same !~~

start the script with (tested with Python 2.7 and 3.4)

```python FAH_WrapperGPUTrajectory.py```  - or - 
```python3.4 FAH_WrapperGPUTrajectory.py```   

Then on a remote machine (or the same) start the viewer; please don't enter localhost:36331 as connection for the viewer; that might case trouble (Thank Davidcoton for pointing that out) 

```FAHViewer --connect=<wrapper_hostname>:36331 --password=<password> --slot=1```

As result something like this should appear (best view seems if you choose '3' in the viewer)
![FAH GPU trajectory](http://imageshack.us/a/img910/339/w1sh5j.jpg)

![FAH GPU trajectory](http://imageshack.com/a/img905/7480/JObdT1.png)

Attention: right now not much more then a proof-of-concept ... still some work to be done ...

And some rough architecture overview

![Architecture](http://imageshack.us/a/img905/2458/cwsF06.jpg)
