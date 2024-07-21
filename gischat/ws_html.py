ws_html = """
<!DOCTYPE html>
<html>
    <head>
        <title>gischat</title>
    </head>
    <body>
        <h1>gischat websocket client</h1>
        <form action="" onsubmit="sendMessage(event)">
            <label>Instance: <input type="text" id="instance" autocomplete="off" value=""/></label>
            <label>Room: <input type="text" id="roomId" autocomplete="off" value="QGIS"/></label>
            <button onclick="connect(event)">Connect</button>
            <hr>
            <label>Author: <input type="text" id="authorId" autocomplete="off" value="geotribu"/></label>
            <label>Message: <input type="text" id="messageText" autocomplete="off"/></label>
            <button>Send</button>
        </form>
        <hr>
        <ul id='messages'>
        </ul>
        <script>
            let ws = null;

            const instance = document.getElementById('instance');
            instance.value = window.location.host;

            function displayMessage(msg){
                const messages = document.getElementById('messages');
                const message = document.createElement('li');
                console.log(msg);
                const content = document.createTextNode(msg);
                message.appendChild(content);
                messages.appendChild(message);
            };
            function connect(event) {
                const instance = document.getElementById("instance");
                const room = document.getElementById("roomId");
                const author = document.getElementById("authorId");
                ws = new WebSocket("wss://" + instance.value + "/room/" + room.value + "/ws");
                ws.onopen = (event) => displayMessage("connection to websocket ok");
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    const log = `[${data.author}] (${new Date().toLocaleTimeString()}): ${data.message}`;
                    displayMessage(log);
                };
                ws.onerror = (error) => displayMessage(error);
                event.preventDefault();
            };
            function sendMessage(event) {
                const message = document.getElementById("messageText");
                const author = document.getElementById("authorId");
                ws.send(JSON.stringify({message: message.value, author: author.value}));
                message.value = ''
                event.preventDefault()
            };
        </script>
    </body>
</html>
"""
