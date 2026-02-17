package com.guaposniper.terminal

import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader

class TerminalSession {

    var currentDirectory: File = File("/sdcard")
        private set

    private val commandHistory = mutableListOf<String>()
    private var historyIndex = -1

    private val aliases = mutableMapOf(
        "ll" to "ls -la",
        "la" to "ls -a",
        "cls" to "clear",
        "q" to "exit"
    )

    private val builtinCommands = setOf("cd", "pwd", "clear", "help", "history", "alias", "whoami", "about", "exit")

    fun execute(input: String): CommandResult {
        val trimmed = input.trim()
        if (trimmed.isEmpty()) return CommandResult("", false)

        commandHistory.add(trimmed)
        historyIndex = commandHistory.size

        // Resolve alias
        val resolved = aliases[trimmed.split(" ")[0]]?.let {
            it + trimmed.removePrefix(trimmed.split(" ")[0])
        } ?: trimmed

        val parts = resolved.split("\\s+".toRegex())
        val command = parts[0]
        val args = parts.drop(1)

        return when (command) {
            "cd" -> handleCd(args)
            "pwd" -> CommandResult(currentDirectory.absolutePath, false)
            "clear" -> CommandResult("", false, clearScreen = true)
            "help" -> handleHelp()
            "history" -> handleHistory()
            "alias" -> handleAlias(args)
            "whoami" -> CommandResult("guaposniper", false)
            "about" -> handleAbout()
            "exit" -> CommandResult("", false, exitApp = true)
            else -> executeShellCommand(resolved)
        }
    }

    private fun handleCd(args: List<String>): CommandResult {
        val target = when {
            args.isEmpty() -> "/sdcard"
            args[0] == "~" -> "/sdcard"
            args[0] == "-" -> currentDirectory.parent ?: "/"
            args[0] == ".." -> currentDirectory.parent ?: "/"
            args[0].startsWith("/") -> args[0]
            else -> "${currentDirectory.absolutePath}/${args[0]}"
        }

        val dir = File(target)
        return if (dir.exists() && dir.isDirectory) {
            currentDirectory = dir
            CommandResult("", false)
        } else {
            CommandResult("cd: $target: Dossier introuvable", true)
        }
    }

    private fun handleHelp(): CommandResult {
        val help = buildString {
            appendLine("╔══════════════════════════════════════╗")
            appendLine("║       GuapoTerminal - Aide           ║")
            appendLine("╠══════════════════════════════════════╣")
            appendLine("║                                      ║")
            appendLine("║  Commandes internes:                 ║")
            appendLine("║    cd <dir>    - Changer de dossier   ║")
            appendLine("║    pwd         - Dossier actuel       ║")
            appendLine("║    clear       - Effacer l'écran      ║")
            appendLine("║    history     - Historique            ║")
            appendLine("║    alias       - Voir les alias       ║")
            appendLine("║    whoami      - Utilisateur actuel   ║")
            appendLine("║    about       - À propos             ║")
            appendLine("║    help        - Cette aide           ║")
            appendLine("║    exit        - Quitter              ║")
            appendLine("║                                      ║")
            appendLine("║  Commandes shell:                    ║")
            appendLine("║    ls, cat, mkdir, rm, cp, mv,       ║")
            appendLine("║    touch, chmod, find, grep,         ║")
            appendLine("║    echo, date, df, du, ping,         ║")
            appendLine("║    wget, curl, ip, ifconfig...       ║")
            appendLine("║                                      ║")
            appendLine("╚══════════════════════════════════════╝")
        }
        return CommandResult(help.trimEnd(), false)
    }

    private fun handleHistory(): CommandResult {
        if (commandHistory.isEmpty()) {
            return CommandResult("Historique vide.", false)
        }
        val output = commandHistory.mapIndexed { i, cmd ->
            "  ${i + 1}  $cmd"
        }.joinToString("\n")
        return CommandResult(output, false)
    }

    private fun handleAlias(args: List<String>): CommandResult {
        if (args.isEmpty()) {
            if (aliases.isEmpty()) return CommandResult("Aucun alias défini.", false)
            val output = aliases.map { (k, v) -> "  $k='$v'" }.joinToString("\n")
            return CommandResult(output, false)
        }

        val definition = args.joinToString(" ")
        val eqIndex = definition.indexOf('=')
        if (eqIndex == -1) {
            return CommandResult("Usage: alias nom=commande", true)
        }

        val name = definition.substring(0, eqIndex).trim()
        val value = definition.substring(eqIndex + 1).trim().removeSurrounding("'").removeSurrounding("\"")
        aliases[name] = value
        return CommandResult("Alias ajouté: $name='$value'", false)
    }

    private fun handleAbout(): CommandResult {
        val about = buildString {
            appendLine("  ╔═══════════════════════════════╗")
            appendLine("  ║     ★ GuapoTerminal v1.0 ★    ║")
            appendLine("  ║                               ║")
            appendLine("  ║   Terminal Android perso      ║")
            appendLine("  ║   par GuapoSniper             ║")
            appendLine("  ║                               ║")
            appendLine("  ║   github.com/guaposniper      ║")
            appendLine("  ╚═══════════════════════════════╝")
        }
        return CommandResult(about.trimEnd(), false)
    }

    private fun executeShellCommand(command: String): CommandResult {
        return try {
            val process = ProcessBuilder("sh", "-c", command)
                .directory(currentDirectory)
                .redirectErrorStream(true)
                .start()

            val reader = BufferedReader(InputStreamReader(process.inputStream))
            val output = StringBuilder()

            var line: String?
            var lineCount = 0
            while (reader.readLine().also { line = it } != null && lineCount < 5000) {
                output.appendLine(line)
                lineCount++
            }

            if (lineCount >= 5000) {
                output.appendLine("... (sortie tronquée à 5000 lignes)")
            }

            process.waitFor()
            val exitCode = process.exitValue()

            CommandResult(
                output.toString().trimEnd(),
                exitCode != 0
            )
        } catch (e: Exception) {
            CommandResult("Erreur: ${e.message}", true)
        }
    }

    fun getPreviousCommand(): String? {
        if (commandHistory.isEmpty()) return null
        historyIndex = (historyIndex - 1).coerceAtLeast(0)
        return commandHistory[historyIndex]
    }

    fun getNextCommand(): String? {
        if (commandHistory.isEmpty()) return null
        historyIndex = (historyIndex + 1).coerceAtMost(commandHistory.size)
        return if (historyIndex < commandHistory.size) commandHistory[historyIndex] else ""
    }

    fun getPrompt(): String = "${shortenPath(currentDirectory.absolutePath)} $"

    private fun shortenPath(path: String): String {
        return path
            .replace("/storage/emulated/0", "~")
            .replace("/sdcard", "~")
    }
}

data class CommandResult(
    val output: String,
    val isError: Boolean,
    val clearScreen: Boolean = false,
    val exitApp: Boolean = false
)
