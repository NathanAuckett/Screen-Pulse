
## Screen Pulse
Screen Pulse is a screen sharing app purposefully designed to share a constant stream of screenshots instead of video to provide a fast, low frame-rate view of a remote display. Think live time-lapse style screen sharing.

It was built to allow for live monitoring of a remote desktop display with content that only changes once every few seconds and thus a higher frame-rate video feed would be a waste of system and network resources.

A port-forward or similar setup is required to make the network connection if the remote display is not on the same network as the client application.

<br>

### Server app
The Server app takes a screenshot once every X milliseconds and acts as a simple HTTP server, awaiting a request from one or more Clients.

![Server app preview](.\docs\Server.png)

<br>

### Client app
The Client app requests new images from the Server app every X milliseconds and displays the received image.

It's possible to adjust the Client behavior via the on-screen UI and more extensively via the config file located in "\AppData\Roaming\Screen Pulse".
The on-screen UI options can be hidden with F1 to make full use of the window size to display the received image.

![Client app preview](.\docs\Client.png)

<br>

### Note for other devs
Screen Pulse is my introduction and first attempt at using the Python programming language. The code is likely unoptimized and/or poorly written.