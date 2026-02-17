package com.guaposniper.terminal;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.method.ScrollingMovementMethod;
import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private TextView terminalOutput;
    private EditText terminalInput;
    private ScrollView scrollView;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private File currentDir;
    private StringBuilder outputBuffer = new StringBuilder();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        terminalOutput = findViewById(R.id.terminal_output);
        terminalInput = findViewById(R.id.terminal_input);
        scrollView = findViewById(R.id.scroll_view);

        terminalOutput.setMovementMethod(new ScrollingMovementMethod());
        currentDir = getFilesDir();

        appendOutput("╔══════════════════════════════════════╗\n");
        appendOutput("║       GuapoTerminal v1.0             ║\n");
        appendOutput("║   by GuapoSniper                     ║\n");
        appendOutput("║   Ton terminal perso Android          ║\n");
        appendOutput("╚══════════════════════════════════════╝\n\n");
        showPrompt();

        terminalInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_DONE ||
                (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                 && event.getAction() == KeyEvent.ACTION_DOWN)) {
                String command = terminalInput.getText().toString().trim();
                if (!command.isEmpty()) {
                    executeCommand(command);
                    terminalInput.setText("");
                }
                return true;
            }
            return false;
        });
    }

    private void showPrompt() {
        String dirName = currentDir.getName();
        if (dirName.isEmpty()) dirName = "/";
        appendOutput("guapo@terminal:" + dirName + "$ ");
    }

    private void executeCommand(String command) {
        appendOutput(command + "\n");

        // Handle built-in commands
        if (command.equals("clear") || command.equals("cls")) {
            outputBuffer = new StringBuilder();
            mainHandler.post(() -> terminalOutput.setText(""));
            showPrompt();
            return;
        }

        if (command.equals("help")) {
            showHelp();
            showPrompt();
            return;
        }

        if (command.equals("exit")) {
            finish();
            return;
        }

        if (command.equals("pwd")) {
            appendOutput(currentDir.getAbsolutePath() + "\n");
            showPrompt();
            return;
        }

        if (command.startsWith("cd ")) {
            changeDirectory(command.substring(3).trim());
            showPrompt();
            return;
        }

        if (command.equals("whoami")) {
            appendOutput("guaposniper\n");
            showPrompt();
            return;
        }

        if (command.equals("neofetch")) {
            showNeofetch();
            showPrompt();
            return;
        }

        // Execute shell command
        executor.execute(() -> {
            try {
                ProcessBuilder pb = new ProcessBuilder("sh", "-c", command);
                pb.directory(currentDir);
                pb.redirectErrorStream(true);
                Process process = pb.start();

                BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream())
                );

                String line;
                while ((line = reader.readLine()) != null) {
                    final String output = line;
                    mainHandler.post(() -> appendOutput(output + "\n"));
                }

                process.waitFor();
                reader.close();

            } catch (Exception e) {
                mainHandler.post(() ->
                    appendOutput("Erreur: " + e.getMessage() + "\n")
                );
            }

            mainHandler.post(this::showPrompt);
        });
    }

    private void changeDirectory(String path) {
        File newDir;
        if (path.equals("..")) {
            newDir = currentDir.getParentFile();
            if (newDir == null) newDir = currentDir;
        } else if (path.startsWith("/")) {
            newDir = new File(path);
        } else {
            newDir = new File(currentDir, path);
        }

        if (newDir.exists() && newDir.isDirectory()) {
            currentDir = newDir;
        } else {
            appendOutput("cd: " + path + ": Dossier introuvable\n");
        }
    }

    private void showHelp() {
        appendOutput("\n");
        appendOutput("╔══ GuapoTerminal - Commandes ══╗\n");
        appendOutput("║                                ║\n");
        appendOutput("║  help     - Afficher l'aide    ║\n");
        appendOutput("║  clear    - Effacer l'ecran    ║\n");
        appendOutput("║  pwd      - Dossier actuel     ║\n");
        appendOutput("║  cd <dir> - Changer dossier    ║\n");
        appendOutput("║  ls       - Lister fichiers    ║\n");
        appendOutput("║  whoami   - Ton nom            ║\n");
        appendOutput("║  neofetch - Info systeme       ║\n");
        appendOutput("║  exit     - Quitter            ║\n");
        appendOutput("║                                ║\n");
        appendOutput("║  + toutes les commandes shell  ║\n");
        appendOutput("╚════════════════════════════════╝\n\n");
    }

    private void showNeofetch() {
        String model = android.os.Build.MODEL;
        String brand = android.os.Build.BRAND;
        String version = android.os.Build.VERSION.RELEASE;
        int sdk = android.os.Build.VERSION.SDK_INT;

        appendOutput("\n");
        appendOutput("   ██████╗ ██╗   ██╗ █████╗ ██████╗  ██████╗ \n");
        appendOutput("  ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔═══██╗\n");
        appendOutput("  ██║  ███╗██║   ██║███████║██████╔╝██║   ██║\n");
        appendOutput("  ██║   ██║██║   ██║██╔══██║██╔═══╝ ██║   ██║\n");
        appendOutput("  ╚██████╔╝╚██████╔╝██║  ██║██║     ╚██████╔╝\n");
        appendOutput("   ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝      ╚═════╝\n");
        appendOutput("  ─────────────────────────────────────\n");
        appendOutput("  OS:      Android " + version + " (SDK " + sdk + ")\n");
        appendOutput("  Device:  " + brand + " " + model + "\n");
        appendOutput("  Shell:   GuapoTerminal v1.0\n");
        appendOutput("  User:    guaposniper\n");
        appendOutput("  ─────────────────────────────────────\n\n");
    }

    private void appendOutput(String text) {
        outputBuffer.append(text);
        terminalOutput.setText(outputBuffer.toString());
        scrollView.post(() -> scrollView.fullScroll(ScrollView.FOCUS_DOWN));
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
