// Firebase settings for the shared "stamhad-accounts" project.
// These values are public (they identify the project; the security rules protect the data).
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    switch (defaultTargetPlatform) {
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return ios;
      default:
        return android;
    }
  }

  static const String _projectId = 'stamhad-accounts';
  static const String _apiKey = 'AIzaSyDO-_gyJXTyBQzdfXQ56T2w8z716FgCM3k';
  static const String _senderId = '1040575713218';
  static const String _dbUrl = 'https://stamhad-accounts-default-rtdb.firebaseio.com';

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: _apiKey,
    appId: '1:1040575713218:android:b34a9541c74a839e52505b',
    messagingSenderId: _senderId,
    projectId: _projectId,
    databaseURL: _dbUrl,
    storageBucket: 'stamhad-accounts.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: _apiKey,
    appId: '1:1040575713218:ios:9217d876ef99004052505b',
    messagingSenderId: _senderId,
    projectId: _projectId,
    databaseURL: _dbUrl,
    storageBucket: 'stamhad-accounts.firebasestorage.app',
    iosBundleId: 'com.stamhad.nume',
  );
}
