package com.vertexerp.mobile

import io.flutter.embedding.android.FlutterFragmentActivity

// FlutterFragmentActivity (nao FlutterActivity) porque o local_auth
// precisa de uma FragmentActivity pra mostrar o prompt de biometria.
class MainActivity : FlutterFragmentActivity()
