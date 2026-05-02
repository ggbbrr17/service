import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:math' as math;

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
        scaffoldBackgroundColor: Colors.transparent,
        primaryColor: const Color(0xFF00FF41),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(20)),
          ),
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

class WaterWavePainter extends CustomPainter {
  final double waveValue;
  final Color color;

  WaterWavePainter(this.waveValue, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withAlpha(30)
      ..style = PaintingStyle.fill;
    
    final linePaint = Paint()
      ..color = color.withAlpha(120)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;

    final path = Path();
    final yOffset = size.height * 0.6; 
    final waveHeight = 5.0;

    path.moveTo(0, size.height);
    path.lineTo(0, yOffset);
    for (double i = 0; i <= size.width; i++) {
      path.lineTo(i, yOffset + math.sin((i / size.width * 2 * math.pi) + (waveValue * 2 * math.pi)) * waveHeight);
    }
    path.lineTo(size.width, size.height);
    path.close();
    canvas.drawPath(path, paint);

    // Dibujar línea de superficie del agua
    final surfacePath = Path();
    surfacePath.moveTo(0, yOffset + math.sin(waveValue * 2 * math.pi) * waveHeight);
    for (double i = 0; i <= size.width; i++) {
      surfacePath.lineTo(i, yOffset + math.sin((i / size.width * 2 * math.pi) + (waveValue * 2 * math.pi)) * waveHeight);
    }
    canvas.drawPath(surfacePath, linePaint);
  }

  @override
  bool shouldRepaint(WaterWavePainter oldDelegate) => true;
}

class PixelPainter extends CustomPainter {
  final double animationValue;
  PixelPainter(this.animationValue);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.blueAccent.withAlpha(180);
    final random = math.Random(123); // Semilla fija para consistencia
    for (int i = 0; i < 15; i++) {
      final x = random.nextDouble() * size.width;
      final speed = 0.6 + random.nextDouble();
      final y = (size.height - (animationValue * speed * size.height)) % size.height;
      canvas.drawRect(Rect.fromLTWH(x, y, 1.5, 1.5), paint);
    }
  }

  @override
  bool shouldRepaint(PixelPainter oldDelegate) => true;
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with TickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, dynamic>> _messages = [];
  bool _isThinking = false;
  bool _isExpanded = false;
  String _lastResponse = "";
  late AnimationController _pulseController;
  late AnimationController _rotationController;
  late Animation<double> _rotationCurve;
  late AnimationController _waveController;
  late AnimationController _entryController;
  late Animation<double> _entryScale;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    _rotationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 5),
    )..repeat();

    _rotationCurve = CurvedAnimation(
      parent: _rotationController,
      curve: Curves.easeInOutSine,
    );

    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();

    _entryController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    _entryScale = CurvedAnimation(
      parent: _entryController,
      curve: Curves.elasticOut,
    );

    _entryController.forward();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _rotationController.dispose();
    _waveController.dispose();
    _entryController.dispose();
    _controller.dispose();
    super.dispose();
  }

  final String apiUrl = "http://192.168.1.7:5000/api/v1/ask";
  final String secret = "glyph123";

  Future<void> _handleSend() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    _controller.clear();
    setState(() {
      _isExpanded = false;
      _lastResponse = "";
      _messages.add({"role": "user", "text": text});
      _isThinking = true;
    });

    try {
      final response = await http
          .post(
            Uri.parse(apiUrl),
            headers: {
              "Content-Type": "application/json",
              "X-Glyph-Secret": secret,
            },
            body: jsonEncode({"question": text}),
          )
          .timeout(const Duration(seconds: 45));

      if (response.statusCode == 200) {
        if (response.body.isNotEmpty) {
          final data = jsonDecode(response.body);
          setState(() {
            _messages.add({
              "role": "glyph",
              "text": data['message'] ?? "Sin respuesta de texto.",
              "model": data['active_model'] ?? "GLYPH",
            });
            _lastResponse = data['message'] ?? "";
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
    final screenWidth = MediaQuery.of(context).size.width;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          Positioned(
            top: 40,
            right: 20,
            child: IconButton(
              icon: const Icon(
                Icons.refresh,
                color: Colors.transparent,
                size: 20,
              ),
              onPressed: () => setState(() => _messages.clear()),
            ),
          ),

          Align(
            alignment: Alignment.bottomCenter,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_lastResponse.isNotEmpty && !_isExpanded)
                  Padding(
                    padding: const EdgeInsets.only(
                      bottom: 20,
                      left: 30,
                      right: 30,
                    ),
                    child: AnimatedOpacity(
                      opacity: _isThinking ? 0.3 : 1.0,
                      duration: const Duration(milliseconds: 600),
                      child: Text(
                        _lastResponse,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Color(0xFF00FF41),
                          fontSize: 17,
                          fontWeight: FontWeight.w300,
                          letterSpacing: 0.5,
                          shadows: [
                            Shadow(
                              color: Colors.black,
                              blurRadius: 12,
                              offset: Offset(0, 2),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                GestureDetector(
                  onTap: () => setState(() => _isExpanded = true),
                  child: AnimatedBuilder(
                    animation: Listenable.merge([
                      _pulseController,
                      _rotationController,
                      _waveController,
                      _entryController,
                    ]),
                    builder: (context, child) {
                      double pulse = _pulseController.value;
                      double scale = _isExpanded 
                          ? 1.0 
                          : (1.0 + (pulse * 0.08)) * _entryScale.value;

                      return Stack(
                        alignment: Alignment.center,
                        children: [
                          if (!_isExpanded)
                            RotationTransition(
                              turns: _rotationCurve,
                              child: Container(
                                width: 105,
                                height: 105,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: Colors.blueAccent.withAlpha(_isThinking ? 100 : 30),
                                    width: 0.8,
                                  ),
                                ),
                              ),
                            ),

                          Transform.scale(
                            scale: scale,
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 400),
                              curve: Curves.easeInOutBack,
                              width: _isExpanded ? screenWidth * 0.85 : 85,
                              height: 85,
                              decoration: BoxDecoration(
                                shape: _isExpanded
                                    ? BoxShape.rectangle
                                    : BoxShape.circle,
                                borderRadius: _isExpanded
                                    ? BorderRadius.circular(40)
                                    : null,
                                border: Border.all(
                                  color: Colors.blue.withAlpha(50),
                                  width: 1.0,
                                ),
                                gradient: _isExpanded
                                    ? null
                                    : RadialGradient(
                                        center: Alignment.center,
                                        radius: 0.9,
                                        colors: [
                                          Colors.blue.withAlpha(15),
                                          Colors.transparent,
                                        ],
                                      ),
                                color: _isExpanded ? Colors.black.withAlpha(220) : Colors.transparent,
                                boxShadow: [
                                  if (!_isExpanded)
                                    BoxShadow(
                                      color: Colors.blueAccent.withAlpha(_isThinking ? 80 : 30),
                                      blurRadius: 15,
                                      spreadRadius: pulse * 2,
                                    ),
                                  if (!_isExpanded)
                                    const BoxShadow(
                                      color: Colors.black54,
                                      offset: Offset(4, 8),
                                      blurRadius: 10,
                                    ),
                                ],
                              ),
                              child: _isExpanded
                                  ? Padding(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 20,
                                      ),
                                      child: TextField(
                                        controller: _controller,
                                        autofocus: true,
                                        style: const TextStyle(
                                          color: Color(0xFF00FF41),
                                          fontSize: 18,
                                        ),
                                        decoration: const InputDecoration(
                                          hintText: "Glyph está escuchando...",
                                          hintStyle: TextStyle(
                                            color: Colors.white24,
                                          ),
                                          border: InputBorder.none,
                                          focusedBorder: InputBorder.none,
                                          enabledBorder: InputBorder.none,
                                        ),
                                        onSubmitted: (_) => _handleSend(),
                                      ),
                                    )
                                  : ClipOval(
                                      child: Stack(
                                        children: [
                                          CustomPaint(
                                            painter: WaterWavePainter(
                                              _waveController.value,
                                              Colors.blueAccent,
                                            ),
                                            size: Size.infinite,
                                          ),
                                          if (_isThinking)
                                            CustomPaint(
                                              painter: PixelPainter(_waveController.value),
                                              size: Size.infinite,
                                            ),
                                        ],
                                      ),
                                    ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
                const SizedBox(
                  height: 50,
                ), 
              ],
            ),
          ),
        ],
      ),
    );
  }
}
