import SwiftUI

// MARK: - Modelos
struct Message: Identifiable, Codable {
    var id = UUID()
    let text: String
    let isUser: Bool
    let emotion: String?
    
    enum CodingKeys: String, CodingKey {
        case text = "message"
        case emotion
    }
    
    init(text: String, isUser: Bool, emotion: String? = nil) {
        self.text = text
        self.isUser = isUser
        self.emotion = emotion
    }
}

// MARK: - ViewModel
class GlyphViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isTyping = false
    
    private let serverURL = "https://tu-servidor-glyph.render.com/ask" // Cambiar por tu URL de producción o LocalTunnel

    func sendCommand(_ question: String) {
        let userMessage = Message(text: question, isUser: true)
        messages.append(userMessage)
        
        isTyping = true
        
        guard let url = URL(string: serverURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["question": question]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, _, error in
            DispatchQueue.main.async {
                self.isTyping = false
                if let data = data {
                    if let response = try? JSONDecoder().decode(Message.self, from: data) {
                        self.messages.append(Message(text: response.text, isUser: false, emotion: response.emotion))
                    }
                } else if let error = error {
                    self.messages.append(Message(text: "Error de conexión: \(error.localizedDescription)", isUser: false))
                }
            }
        }.resume()
    }
}

// MARK: - UI Principal
struct ContentView: View {
    @StateObject var viewModel = GlyphViewModel()
    @State private var inputText = ""
    
    var body: some View {
        NavigationView {
            VStack {
                // Lista de mensajes
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(viewModel.messages) { msg in
                                ChatBubble(message: msg)
                            }
                        }
                        .padding()
                    }
                }
                
                if viewModel.isTyping {
                    Text("Glyph está pensando...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Barra de entrada
                HStack {
                    TextField("Habla con Glyph...", text: $inputText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .padding(.horizontal)
                    
                    Button(action: {
                        guard !inputText.isEmpty else { return }
                        viewModel.sendCommand(inputText)
                        inputText = ""
                    }) {
                        Image(systemName: "paperplane.fill")
                            .foregroundColor(.blue)
                            .padding(.trailing)
                    }
                }
                .padding(.bottom)
            }
            .navigationTitle("Glyph iOS")
        }
    }
}

struct ChatBubble: View {
    let message: Message
    var body: some View {
        HStack {
            if message.isUser { Spacer() }
            VStack(alignment: message.isUser ? .trailing : .leading) {
                Text(message.text)
                    .padding(12)
                    .background(message.isUser ? Color.blue : Color.gray.opacity(0.15))
                    .foregroundColor(message.isUser ? .white : .primary)
                    .cornerRadius(16)
                if let emotion = message.emotion, !emotion.isEmpty {
                    Text(emotion)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 4)
                }
            }
            if !message.isUser { Spacer() }
        }
    }
}