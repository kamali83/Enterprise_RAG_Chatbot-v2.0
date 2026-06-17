let token = "";
let conversations = {};
let currentTab = null;
let currentUser = "";
let userId = null;
let conversationId = null;

// API Base URL
const API_BASE = "/api";

// ===== Auth =====
function showAuthMessage(text, type) {
    const el = document.getElementById("auth-message");
    el.textContent = text;
    el.className = "auth-message " + type;
    el.style.display = "block";
    setTimeout(() => { el.style.display = "none"; }, 4000);
}

async function signup() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    if (!username || !password) {
        showAuthMessage("Please fill in both fields.", "error");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            showAuthMessage("Account created! You can now log in.", "success");
        } else {
            showAuthMessage(data.detail || "Signup failed.", "error");
        }
    } catch (err) {
        console.error("Signup error:", err);
        showAuthMessage("Network error. Please try again.", "error");
    }
}

async function login() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    if (!username || !password) {
        showAuthMessage("Please fill in both fields.", "error");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            token = data.access_token;
            currentUser = username;
            userId = data.user_id;
            document.getElementById("auth-screen").style.display = "none";
            document.getElementById("chat-screen").style.display = "flex";
            document.getElementById("user-badge").textContent = "👤 " + username;
            loadConversations();
            document.getElementById("query").focus();
        } else {
            showAuthMessage(data.detail || "Invalid credentials.", "error");
        }
    } catch (err) {
        console.error("Login error:", err);
        showAuthMessage("Network error. Please try again.", "error");
    }
}

// ===== Conversations =====
async function loadConversations() {
    try {
        const res = await fetch(`${API_BASE}/conversations`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (data.length > 0) {
            // Load conversations from database
            data.forEach(conv => {
                conversations[conv.id] = { dbId: conv.id, name: conv.name, messages: [] };
            });
            // Select the most recent conversation
            currentTab = Object.keys(conversations)[0];
            await loadMessages(currentTab);
        } else {
            // No existing conversations, create new
            await newConversation();
        }
        renderTabs();
        renderMessages();
    } catch (err) {
        console.error("Load conversations error:", err);
    }
}

async function loadMessages(convId) {
    const conv = conversations[convId];
    if (!conv) return;

    try {
        const res = await fetch(`${API_BASE}/conversations/${conv.dbId}/messages`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        // Check if response is JSON
        const contentType = res.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            console.error("Non-JSON response from messages endpoint");
            conv.messages = [];
            renderMessages();
            return;
        }
        
        const data = await res.json();
        conv.messages = data.map(m => ({ type: m.sender, text: m.content }));
        renderMessages();
    } catch (err) {
        console.error("Load messages error:", err);
        conv.messages = [];
        renderMessages();
    }
}

async function newConversation() {
    const id = "conv-" + Date.now();
    try {
        const res = await fetch(`${API_BASE}/conversations`, {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ name: "New Chat " + Object.keys(conversations).length })
        });
        const data = await res.json();
        if (res.ok) {
            conversations[data.id] = { dbId: data.id, name: data.name, messages: [] };
            currentTab = data.id;
            conversationId = data.id;
            renderTabs();
            renderMessages();
            document.getElementById("query").focus();
        }
    } catch (err) {
        console.error("New conversation error:", err);
    }
}

function renderTabs() {
    const tabsDiv = document.getElementById("tabs");
    tabsDiv.innerHTML = "";
    const ids = Object.keys(conversations);
    ids.forEach((id, index) => {
        const conv = conversations[id];
        const tabContainer = document.createElement("div");
        tabContainer.className = "tab-container";

        const tab = document.createElement("div");
        tab.className = "tab" + (id === currentTab ? " active" : "");
        tab.textContent = "💬 " + (conv.name || "Chat " + (index + 1));
        tab.onclick = () => {
            currentTab = id;
            renderTabs();
            renderMessages();
        };

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "tab-delete";
        deleteBtn.innerHTML = "&times;";
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteConversation(id);
        };

        tabContainer.appendChild(tab);
        tabContainer.appendChild(deleteBtn);
        tabsDiv.appendChild(tabContainer);
    });
}

async function deleteConversation(convId) {
    try {
        const conv = conversations[convId];
        if (!conv || !conv.dbId) {
            delete conversations[convId];
            if (currentTab === convId) {
                currentTab = Object.keys(conversations)[0];
            }
            renderTabs();
            renderMessages();
            return;
        }

        const res = await fetch(`${API_BASE}/conversations/${conv.dbId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            delete conversations[convId];
            if (currentTab === convId) {
                currentTab = Object.keys(conversations)[0];
                if (currentTab) {
                    await loadMessages(currentTab);
                } else {
                    await newConversation();
                }
            }
            renderTabs();
            renderMessages();
        }
    } catch (err) {
        console.error("Delete conversation error:", err);
    }
}

// ===== Messages =====
function renderMessages() {
    const messagesDiv = document.getElementById("messages");
    messagesDiv.innerHTML = "";

    if (!currentTab || !conversations[currentTab] || conversations[currentTab].messages.length === 0) {
        messagesDiv.innerHTML = `
            <div class="welcome-msg" id="welcome-msg">
                <div class="welcome-icon">💬</div>
                <h2>Welcome${currentUser ? ', ' + currentUser : ''}!</h2>
                <p>Ask me anything about your documents. I'll find the most relevant information for you.</p>
            </div>`;
        return;
    }

    conversations[currentTab].messages.forEach(msg => {
        const row = document.createElement("div");
        row.className = "msg-row " + msg.type;

        const avatar = document.createElement("div");
        avatar.className = "msg-avatar";
        avatar.textContent = msg.type === "user" ? "U" : "AI";

        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";
        bubble.textContent = msg.text;

        if (msg.type === "bot") {
            row.appendChild(avatar);
            row.appendChild(bubble);
        } else {
            row.appendChild(bubble);
            row.appendChild(avatar);
        }

        messagesDiv.appendChild(row);
    });

    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showTypingIndicator() {
    const messagesDiv = document.getElementById("messages");
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.id = "typing-row";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "AI";

    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.innerHTML = "<span></span><span></span><span></span>";

    row.appendChild(avatar);
    row.appendChild(indicator);
    messagesDiv.appendChild(row);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typing-row");
    if (el) el.remove();
}

// ===== Send Query =====
async function sendQuery() {
    const queryInput = document.getElementById("query");
    const query = queryInput.value.trim();
    if (!query || !currentTab) return;

    const conv = conversations[currentTab];

    // Save user message to database
    try {
        await fetch(`${API_BASE}/conversations/${conv.dbId}/messages`, {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                sender: "user",
                content: query
            })
        });
    } catch (e) {
        console.log("Could not save user message:", e);
    }

    conv.messages.push({ type: "user", text: query });
    renderMessages();
    queryInput.value = "";
    queryInput.focus();

    showTypingIndicator();

    try {
        // First get the answer via regular fetch (non-streaming for simplicity)
        const res = await fetch(`${API_BASE}/ask?query=${encodeURIComponent(query)}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        // Check content type
        const contentType = res.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            console.error("Non-JSON response from ask endpoint");
            removeTypingIndicator();
            conv.messages.push({ type: "bot", text: "Error: Server returned invalid response. Please try again." });
            renderMessages();
            return;
        }
        
        const data = await res.json();
        
        removeTypingIndicator();
        
        let botMessage = { type: "bot", text: data.answer || "No answer received", sources: data.sources || [] };
        conv.messages.push(botMessage);
        renderMessages();

        // Get the bubble element for the new message
        const messagesDiv = document.getElementById("messages");
        const botRow = messagesDiv.lastElementChild;
        const bubble = botRow.querySelector(".msg-bubble");

        // Simulate streaming effect by revealing text character by character
        if (data.answer) {
            bubble.textContent = "";
            const words = data.answer.split(" ");
            for (let i = 0; i < words.length; i++) {
                await new Promise(resolve => setTimeout(resolve, 50));
                bubble.textContent += words[i] + " ";
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }

        // Render sources if available
        if (data.sources && data.sources.length > 0) {
            renderSources(botRow, data.sources);
        }

        // Save bot response to database
        try {
            await fetch(`${API_BASE}/conversations/${conv.dbId}/messages`, {
                method: "POST",
                headers: { 
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    sender: "bot",
                    content: botMessage.text
                })
            });
        } catch (e) {
            console.log("Could not save bot message:", e);
        }

    } catch (err) {
        console.error("Query error:", err);
        removeTypingIndicator();
        conv.messages.push({ type: "bot", text: "Network error. Please try again." });
        renderMessages();
    }
}

// ===== Render Sources =====
function renderSources(rowElement, sources) {
    const sourcesContainer = document.createElement("div");
    sourcesContainer.className = "sources-container";

    const sourcesTitle = document.createElement("div");
    sourcesTitle.className = "sources-title";
    sourcesTitle.textContent = "Sources";

    sourcesContainer.appendChild(sourcesTitle);

    sources.forEach((source, index) => {
        const sourceItem = document.createElement("div");
        sourceItem.className = "source-item";
        sourceItem.innerHTML = `
            <span class="source-number">${index + 1}</span>
            <div class="source-info">
                <span class="source-filename">${source.filename}</span>
                ${source.page ? `<span class="source-page">Page ${source.page}</span>` : ''}
            </div>
        `;
        sourceItem.onclick = () => showSourceModal(source);
        sourcesContainer.appendChild(sourceItem);
    });

    rowElement.appendChild(sourcesContainer);
}

// ===== Source Modal =====
function showSourceModal(source) {
    const modal = document.createElement("div");
    modal.className = "modal-overlay";
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${source.filename} ${source.page ? '- Page ' + source.page : ''}</h3>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <p>${source.content}</p>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.onclick = (e) => {
        if (e.target === modal || e.target.classList.contains('modal-close')) {
            modal.remove();
        }
    };
}

// ===== Enter Key Support =====
document.addEventListener("DOMContentLoaded", () => {
    // Enter to send query
    document.getElementById("query").addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendQuery();
        }
    });

    // Enter to login from auth fields
    document.getElementById("username").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            login();
        }
    });
    document.getElementById("password").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            login();
        }
    });
});

// ===== Document Management =====
async function openDocumentsModal() {
    const modal = document.getElementById("documents-modal");
    modal.style.display = "flex";
    await loadDocuments();
}

function closeDocumentsModal() {
    const modal = document.getElementById("documents-modal");
    modal.style.display = "none";
}

async function loadDocuments() {
    try {
        const res = await fetch(`${API_BASE}/documents`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        renderDocuments(data.documents || data);
    } catch (err) {
        console.error("Load documents error:", err);
        document.getElementById("documents-list").innerHTML = "<p>Failed to load documents</p>";
    }
}

function renderDocuments(documents) {
    const listDiv = document.getElementById("documents-list");
    
    if (!documents || documents.length === 0) {
        listDiv.innerHTML = "<p>No documents uploaded yet.</p>";
        return;
    }
    
    listDiv.innerHTML = documents.map(doc => `
        <div class="document-item">
            <div class="document-info">
                <span class="document-icon">📄</span>
                <div class="document-details">
                    <span class="document-name">${doc.filename}</span>
                    <span class="document-meta">${doc.size || doc.file_size || 0} bytes • ${doc.type || doc.file_type || 'Unknown'}</span>
                </div>
            </div>
            <div class="document-actions">
                <span class="document-status">${doc.indexed ? '✅ Indexed' : '⏳ Pending'}</span>
                <button class="btn-delete-doc" onclick="deleteDocument('${doc.filename}')">🗑️</button>
            </div>
        </div>
    `).join("");
}

async function handleFileUpload(file) {
    if (!file) return;
    
    const uploadArea = document.getElementById("upload-area");
    uploadArea.innerHTML = `<p>Uploading ${file.name}...</p>`;
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const res = await fetch(`${API_BASE}/documents`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData
        });
        
        const data = await res.json();
        
        if (res.ok) {
            uploadArea.innerHTML = `
                <div class="upload-icon">📁</div>
                <p>Drag & drop files here or click to upload</p>
                <p class="upload-hint">Supported: PDF, TXT, DOCX, MD</p>
                <input type="file" id="file-input" accept=".txt,.pdf,.docx,.md" style="display:none;" onchange="handleFileUpload(this.files[0])" />
                <button class="btn btn-primary" onclick="document.getElementById('file-input').click()">Select Files</button>
            `;
            document.getElementById("file-input").addEventListener("change", (e) => handleFileUpload(e.target.files[0]));
            await loadDocuments();
        } else {
            uploadArea.innerHTML += `<p class="error">Upload failed: ${data.detail}</p>`;
        }
    } catch (err) {
        console.error("Upload error:", err);
        uploadArea.innerHTML += `<p class="error">Upload failed</p>`;
    }
}

async function deleteDocument(filename) {
    if (!confirm(`Delete ${filename}?`)) return;
    
    try {
        const res = await fetch(`${API_BASE}/documents/${filename}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (res.ok) {
            await loadDocuments();
        } else {
            alert("Failed to delete document");
        }
    } catch (err) {
        console.error("Delete error:", err);
        alert("Failed to delete document");
    }
}

// Setup file input listener
document.addEventListener("DOMContentLoaded", () => {
    const uploadArea = document.getElementById("upload-area");
    if (uploadArea) {
        uploadArea.addEventListener("click", (e) => {
            if (e.target === uploadArea || e.target.closest("button")) {
                document.getElementById("file-input").click();
            }
        });
        
        const fileInput = document.getElementById("file-input");
        if (fileInput) {
            fileInput.addEventListener("change", (e) => handleFileUpload(e.target.files[0]));
        }
    }
});
