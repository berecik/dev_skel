/// dev_skel Flutter frontend entry point.
///
/// Wires the wrapper-shared layers (config + auth + items + state) into
/// the widget tree:
///
///   1. [AppConfig.load] reads `<wrapper>/.env` (bundled as the
///      `.env` asset by the gen script).
///   2. [TokenStore.instance] hydrates the persisted JWT from secure
///      storage so a cold start keeps the user signed in.
///   3. [ItemsClient] + [StateApi] + [ItemsController] are constructed
///      once and passed down via [AuthScope] / [AppStateScope] —
///      no third-party DI.
///   4. The root [DevSkelApp] swaps between [LoginScreen] and
///      [HomeScreen] based on [TokenStore.isAuthenticated].
///
/// Mirrors the React skel's `App.tsx` composition as closely as
/// Flutter idioms allow.

import 'package:flutter/material.dart';

import 'api/items_client.dart';
import 'auth/auth_scope.dart';
import 'auth/token_store.dart';
import 'config.dart';
import 'controllers/items_controller.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/app_state_scope.dart';
import 'state/app_state_store.dart';
import 'state/state_api.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final config = await AppConfig.load();
  final tokenStore = TokenStore.instance;
  await tokenStore.load();

  final itemsClient = ItemsClient(config: config, tokenStore: tokenStore);
  final stateApi = StateApi(config: config, tokenStore: tokenStore);
  final appStateStore = AppStateStore();
  final itemsController =
      ItemsController(client: itemsClient, tokenStore: tokenStore);

  runApp(
    DevSkelApp(
      config: config,
      tokenStore: tokenStore,
      itemsClient: itemsClient,
      itemsController: itemsController,
      appStateStore: appStateStore,
      stateApi: stateApi,
    ),
  );
}

class DevSkelApp extends StatelessWidget {
  const DevSkelApp({
    super.key,
    required this.config,
    required this.tokenStore,
    required this.itemsClient,
    required this.itemsController,
    required this.appStateStore,
    required this.stateApi,
  });

  final AppConfig config;
  final TokenStore tokenStore;
  final ItemsClient itemsClient;
  final ItemsController itemsController;
  final AppStateStore appStateStore;
  final StateApi stateApi;

  @override
  Widget build(BuildContext context) {
    return AuthScope(
      store: tokenStore,
      child: ListenableBuilder(
        listenable: tokenStore,
        builder: (context, _) {
          final theme = ThemeData(
            colorSchemeSeed: Colors.indigo,
            useMaterial3: true,
          );
          return MaterialApp(
            title: 'dev_skel Flutter',
            theme: theme,
            home: tokenStore.isAuthenticated
                ? AppStateScope(
                    store: appStateStore,
                    tokenStore: tokenStore,
                    stateApi: stateApi,
                    child: HomeScreen(
                      config: config,
                      itemsController: itemsController,
                    ),
                  )
                : Scaffold(
                    appBar: AppBar(title: const Text('dev_skel Flutter')),
                    body: LoginScreen(client: itemsClient),
                  ),
          );
        },
      ),
    );
  }
}
