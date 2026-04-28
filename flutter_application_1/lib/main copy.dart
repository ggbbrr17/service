import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

void main() => runApp(const GlyphMobileApp());

class GlyphMobileApp extends StatelessWidget {
  const GlyphMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Glyph OS Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0A0A),
        primaryColor: const Color(0xFF00FF41),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(20))),
          focusedBorder: OutlineInputBorder(
            borderSide: BorderSide(color: Color(0xFF00FF41)),
            borderRadius: BorderRadius.all(Radius.circular(20)),
          ),
        ),
      ),
      home: const ChatScreen(),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, dynamic>> _messages = [];
  bool _isThinking = false;

  // Configuración de conexión (Ajusta a tu URL de Render o IP local)
  final String apiUrl = "http://192.168.1.7:5000/api/v1/ask";
  final String secret = "glyph123";

  Future<void> _handleSend() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    _controller.clear();
    setState(() {
      _messages.add({"role": "user", "text": text});
      _isThinking = true;
    });

    try {
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {
          "Content-Type": "application/json",
          "X-Glyph-Secret": secret,
        },
        body: jsonEncode({"question": text}),
      ).timeout(const Duration(seconds: 45));

      if (response.statusCode == 200) {
        if (response.body.isNotEmpty) {
          final data = jsonDecode(response.body);
          setState(() {
            _messages.add({
              "role": "glyph",
              "text": data['message'] ?? "Sin respuesta de texto.",
              "model": data['active_model'] ?? "GLYPH"
            });
          });
        } else {
          _showError("Respuesta vacía del servidor");
        }
      } else {
        _showError("Error: ${response.statusCode}");
      }
    } catch (e) {
      _showError("Enlace fallido: $e");
    } finally {
      setState(() => _isThinking = false);
    }
  }

  void _showError(String err) {
    setState(() {
      _messages.add({"role": "glyph", "text": "⚠️ $err"});
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("GLYPH // MOBILE_CORE", style: TextStyle(fontSize: 14, letterSpacing: 1.5)),
        backgroundColor: Colors.black,
        actions: [
          IconButton(icon: const Icon(Icons.refresh, color: Color(0xFF00FF41)), onPressed: () => setState(() => _messages.clear())),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final m = _messages[index];
                final isUser = m["role"] == "user";
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFF222222) : const Color(0xFF001A00),
                      borderRadius: BorderRadius.circular(15),
                      border: !isUser ? const Border(left: BorderSide(color: Color(0xFF00FF41), width: 3)) : null,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(m["text"], style: const TextStyle(color: Colors.white, fontFamily: 'monospace')),
                        if (!isUser) Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text("CORE: ${m["model"]}", style: const TextStyle(fontSize: 9, color: Color(0xFF008F11))),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          if (_isThinking) const LinearProgressIndicator(color: Color(0xFF00FF41), backgroundColor: Colors.transparent),
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.black,
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(hintText: "Enviar comando...", contentPadding: EdgeInsets.symmetric(horizontal: 20)),
                    onSubmitted: (_) => _handleSend(),
                  ),
                ),
                const SizedBox(width: 8),
                FloatingActionButton.small(
                  backgroundColor: const Color(0xFF00FF41),
                  onPressed: _handleSend,
                  child: const Icon(Icons.bolt, color: Colors.black),
                )
              ],
            ),
          ),
        ],
      ),
    );
  }
}