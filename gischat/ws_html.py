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
            <label>SSL: <input type="checkbox" id="ssl" checked/></label>
            <label>Room: <input type="text" id="roomId" autocomplete="off" value="QGIS"/></label>
            <button onclick="connect(event)">Connect</button>
            <hr>
            <label>Author: <input type="text" id="authorId" autocomplete="off" value=""/></label>
            <label>Message: <input type="text" id="messageText" autocomplete="off"/></label>
            <button>Send</button>
        </form>
        <hr>
        <ul id='messages'>
        </ul>
        <script>
            let websocket = null;

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
            function connect(event){
                const instance = document.getElementById("instance");
                const ssl = document.getElementById("ssl");
                const room = document.getElementById("roomId");
                const author = document.getElementById("authorId");
                const ws_protocol = ssl.checked ? "wss" : "ws";
                const ws_url = `${ws_protocol}://${instance.value}/room/${room.value}/ws`;
                console.log(`Connecting websocket at url ${ws_url}`);
                websocket = new WebSocket(ws_url);
                websocket.onopen = (event) => displayMessage("connection to websocket ok");
                websocket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    const log = `[${data.author}] (${new Date().toLocaleTimeString()}): ${data.message}`;
                    displayMessage(log);
                };
                websocket.onerror = (error) => {
                    displayMessage(`Websocket error ${JSON.stringify(error)}`);
                    console.log("Websocket error", error);
                };
                event.preventDefault();
            };
            function sendMessage(event){
                const message = document.getElementById("messageText");
                const author = document.getElementById("authorId");
                if (!message.value || !author.value){
                    alert("Author and message can not be empty");
                    return;
                }
                websocket.send(JSON.stringify({message: message.value, author: author.value}));
                message.value = ''
                event.preventDefault()
            };
        </script>
    </body>
</html>
"""
