document.addEventListener('DOMContentLoaded', function() {
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const voiceBtn = document.getElementById('voice-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const responseAudio = document.getElementById('response-audio');
    
    let isListening = false;
    let recognition;
    
    // Load chat history
    loadChatHistory();
    
    // Initialize voice recognition if available
    if (voiceBtn && 'webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            stopVoiceRecognition();
        };
        
        recognition.onerror = function(event) {
            console.error('Speech recognition error', event.error);
            stopVoiceRecognition();
        };
        
        voiceBtn.addEventListener('click', toggleVoiceRecognition);
    } else if (voiceBtn) {
        voiceBtn.style.display = 'none';
    }
    
    // Send message function
    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addMessageToChat(message, true);
        userInput.value = '';
        
        // Send to server
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error:', data.error);
                addMessageToChat("Sorry, I'm having trouble responding right now.", false);
            } else {
                addMessageToChat(data.response, false);
                
                // Play audio if available
                if (data.audio_url) {
                    responseAudio.src = data.audio_url;
                    responseAudio.play().catch(e => console.log('Audio play failed:', e));
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            addMessageToChat("Sorry, I'm having trouble connecting right now.", false);
        });
    }
    
    // Add message to chat UI
    function addMessageToChat(message, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(isUser ? 'user-message' : 'ai-message');
        
        const messageText = document.createElement('p');
        messageText.textContent = message;
        
        const timestamp = document.createElement('div');
        timestamp.classList.add('timestamp');
        timestamp.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageText);
        messageDiv.appendChild(timestamp);
        
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // Load chat history from server
    function loadChatHistory() {
        fetch('/history')
        .then(response => response.json())
        .then(messages => {
            messages.forEach(msg => {
                addMessageToChat(msg.message, msg.is_user);
            });
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
        });
    }
    
    // Voice recognition functions
    function toggleVoiceRecognition() {
        if (isListening) {
            stopVoiceRecognition();
        } else {
            startVoiceRecognition();
        }
    }
    
    function startVoiceRecognition() {
        if (recognition) {
            recognition.start();
            voiceBtn.classList.add('listening');
            isListening = true;
            voiceBtn.title = 'Listening... Click to stop';
        }
    }
    
    function stopVoiceRecognition() {
        if (recognition) {
            recognition.stop();
            voiceBtn.classList.remove('listening');
            isListening = false;
            voiceBtn.title = 'Click to speak';
        }
    }
    
    // New chat session
    newChatBtn.addEventListener('click', function() {
        if (confirm('Start a new conversation? Your current chat will be saved.')) {
            fetch('/new-session', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    chatHistory.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error starting new session:', error);
            });
        }
    });
    
    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});