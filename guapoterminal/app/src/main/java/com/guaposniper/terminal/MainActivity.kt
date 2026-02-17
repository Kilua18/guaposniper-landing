package com.guaposniper.terminal

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var terminalOutput: TextView
    private lateinit var commandInput: EditText
    private lateinit var sendButton: ImageButton
    private lateinit var scrollView: ScrollView
    private lateinit var promptLabel: TextView
    private lateinit var session: TerminalSession

    private val outputBuffer = SpannableStringBuilder()

    companion object {
        private const val STORAGE_PERMISSION_CODE = 100
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        terminalOutput = findViewById(R.id.terminalOutput)
        commandInput = findViewById(R.id.commandInput)
        sendButton = findViewById(R.id.sendButton)
        scrollView = findViewById(R.id.scrollView)
        promptLabel = findViewById(R.id.promptLabel)

        session = TerminalSession()

        requestStoragePermission()
        showWelcomeBanner()
        updatePrompt()

        sendButton.setOnClickListener { executeCurrentCommand() }

        commandInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                executeCurrentCommand()
                true
            } else {
                false
            }
        }

        commandInput.setOnKeyListener { _, keyCode, event ->
            if (event.action == KeyEvent.ACTION_DOWN) {
                when (keyCode) {
                    KeyEvent.KEYCODE_DPAD_UP -> {
                        session.getPreviousCommand()?.let { commandInput.setText(it) }
                        commandInput.setSelection(commandInput.text.length)
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_DOWN -> {
                        session.getNextCommand()?.let { commandInput.setText(it) }
                        commandInput.setSelection(commandInput.text.length)
                        true
                    }
                    else -> false
                }
            } else {
                false
            }
        }

        commandInput.requestFocus()
    }

    private fun showWelcomeBanner() {
        val banner = buildString {
            appendLine()
            appendLine("  ██████╗ ██╗   ██╗ █████╗ ██████╗  ██████╗ ")
            appendLine("  ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔═══██╗")
            appendLine("  ██║  ███╗██║   ██║███████║██████╔╝██║   ██║")
            appendLine("  ██║   ██║██║   ██║██╔══██║██╔═══╝ ██║   ██║")
            appendLine("  ╚██████╔╝╚██████╔╝██║  ██║██║     ╚██████╔╝")
            appendLine("   ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝      ╚═════╝")
            appendLine("  ████████╗███████╗██████╗ ███╗   ███╗")
            appendLine("  ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║")
            appendLine("     ██║   █████╗  ██████╔╝██╔████╔██║")
            appendLine("     ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║")
            appendLine("     ██║   ███████╗██║  ██║██║ ╚═╝ ██║")
            appendLine("     ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝")
            appendLine()
            appendLine("  ★ GuapoTerminal v1.0 - by GuapoSniper ★")
            appendLine("  Tape 'help' pour voir les commandes.")
            appendLine()
        }
        appendToOutput(banner, Color.parseColor("#00FFCC"))
    }

    private fun executeCurrentCommand() {
        val command = commandInput.text.toString()
        commandInput.setText("")

        val prompt = session.getPrompt()
        appendToOutput("$prompt $command\n", Color.parseColor("#00FFCC"))

        val result = session.execute(command)

        when {
            result.clearScreen -> {
                outputBuffer.clear()
                terminalOutput.text = ""
                showWelcomeBanner()
            }
            result.exitApp -> {
                finish()
            }
            result.output.isNotEmpty() -> {
                val color = if (result.isError) {
                    Color.parseColor("#FF4444")
                } else {
                    Color.parseColor("#E0E0E0")
                }
                appendToOutput(result.output + "\n", color)
            }
        }

        updatePrompt()
        scrollToBottom()
    }

    private fun appendToOutput(text: String, color: Int) {
        val start = outputBuffer.length
        outputBuffer.append(text)
        outputBuffer.setSpan(
            ForegroundColorSpan(color),
            start,
            outputBuffer.length,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        )
        terminalOutput.text = outputBuffer
    }

    private fun updatePrompt() {
        promptLabel.text = session.getPrompt()
    }

    private fun scrollToBottom() {
        scrollView.post {
            scrollView.fullScroll(ScrollView.FOCUS_DOWN)
            commandInput.requestFocus()
        }
    }

    private fun requestStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (!android.os.Environment.isExternalStorageManager()) {
                try {
                    val intent = android.content.Intent(
                        android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION
                    )
                    startActivity(intent)
                } catch (_: Exception) { }
            }
        } else {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(
                        Manifest.permission.READ_EXTERNAL_STORAGE,
                        Manifest.permission.WRITE_EXTERNAL_STORAGE
                    ),
                    STORAGE_PERMISSION_CODE
                )
            }
        }
    }
}
