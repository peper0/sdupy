/*
 * Copyright 2000-2016 JetBrains s.r.o., 2018 Tomasz Łakota
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * This code is mostly copy-pasted from idea/python/src/com/jetbrains/python/actions/PyExecuteSelectionAction.java
 */
package tomek;

import com.google.common.collect.Lists;
import com.intellij.execution.ExecutionHelper;
import com.intellij.execution.console.LanguageConsoleView;
import com.intellij.execution.process.ProcessHandler;
import com.intellij.execution.ui.ExecutionConsole;
import com.intellij.execution.ui.RunContentDescriptor;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.editor.*;
import com.intellij.openapi.editor.ex.util.EditorUtil;
import com.intellij.openapi.module.Module;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.Pair;
import com.intellij.openapi.util.text.StringUtil;
import com.intellij.openapi.wm.IdeFocusManager;
import com.intellij.openapi.wm.ToolWindow;
import com.intellij.psi.PsiDocumentManager;
import com.intellij.psi.PsiFile;
import com.intellij.ui.content.Content;
import com.intellij.ui.content.ContentManager;
import com.intellij.util.Consumer;
import com.intellij.xdebugger.XDebugSession;
import com.intellij.xdebugger.XDebuggerManager;
import com.jetbrains.python.console.*;
import com.jetbrains.python.psi.PyFile;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

import java.util.Collection;
import java.util.List;

public class PyExecuteRegionAction extends AnAction {

    public static final String EXECUTE_REGION_IN_CONSOLE = "Execute region in Console";

    public PyExecuteRegionAction() {
        super(EXECUTE_REGION_IN_CONSOLE);
    }

    public void actionPerformed(AnActionEvent e) {
        Editor editor = CommonDataKeys.EDITOR.getData(e.getDataContext());
        if (editor != null) {
            final String code = getRegionText(editor);
            if (code != null) {
                String annotated_code = "#" + editor.getProject().getProjectFilePath() +
                        ":" + String.valueOf(editor.getCaretModel().getLogicalPosition().line) + "\n" + code;
                showConsoleAndExecuteCode(e, annotated_code);
            }
        }
    }

    /**
     * Finds existing or creates a new console and then executes provided code there.
     *
     * @param e
     * @param selectionText null means that there is no code to execute, only open a console
     */
    public static void showConsoleAndExecuteCode(@NotNull final AnActionEvent e, @Nullable final String selectionText) {
        final Editor editor = CommonDataKeys.EDITOR.getData(e.getDataContext());
        Project project = e.getProject();
        Module module = e.getData(LangDataKeys.MODULE);

        findCodeExecutor(e, codeExecutor -> executeInConsole(codeExecutor, selectionText, editor), editor, project, module);
    }

    @Nullable
    private static String getRegionText(@NotNull Editor editor) {
        int bestRegionStart=-1;
        int bestRegionEnd=-1;
        int caretOffset = editor.getCaretModel().getOffset();
        for(FoldRegion i : editor.getFoldingModel().getAllFoldRegions()) {
            if(caretOffset >= i.getStartOffset() && caretOffset < i.getEndOffset()) {
                if (i.getStartOffset() > bestRegionStart) {
                    bestRegionStart = i.getStartOffset();
                    bestRegionEnd = i.getEndOffset();
                }
            }
//            Messages.showMessageDialog(editor.getProject(), i.getPlaceholderText(), "heje", Messages.getInformationIcon());
        }
        if(bestRegionStart >= 0) {
            return editor.getDocument().getCharsSequence().subSequence(bestRegionStart, bestRegionEnd).toString();
        }
        else {
            return null;
        }
    }

    public void update(AnActionEvent e) {
        Editor editor = CommonDataKeys.EDITOR.getData(e.getDataContext());
        Presentation presentation = e.getPresentation();

        boolean enabled = false;
        if (editor != null && isPython(editor)) {
            String text = getRegionText(editor);
            enabled = !StringUtil.isEmpty(text);
        }

        presentation.setEnabled(enabled);
        //presentation.setVisible(enabled);
    }

    public static boolean isPython(Editor editor) {
        if (editor == null) {
            return false;
        }

        Project project = editor.getProject();

        if (project == null) {
            return false;
        }

        PsiFile psi = PsiDocumentManager.getInstance(project).getPsiFile(editor.getDocument());
        return psi instanceof PyFile;
    }

    private static void selectConsole(@NotNull DataContext dataContext, @NotNull Project project,
                                      @NotNull final Consumer<PyCodeExecutor> consumer, @Nullable Editor editor) {
        Collection<RunContentDescriptor> consoles = getConsoles(project);

        ExecutionHelper
                .selectContentDescriptor(dataContext, project, consoles, "Select console to execute in", descriptor -> {
                    if (descriptor != null && descriptor.getExecutionConsole() instanceof PyCodeExecutor) {
                        ExecutionConsole console = descriptor.getExecutionConsole();
                        consumer.consume((PyCodeExecutor)console);
                        if (console instanceof PythonDebugLanguageConsoleView) {
                            XDebugSession currentSession = XDebuggerManager.getInstance(project).getCurrentSession();
                            if (currentSession != null) {
                                // Select "Console" tab in case of Debug console
                                ContentManager contentManager = currentSession.getUI().getContentManager();
                                Content content = contentManager.findContent("Console");
                                contentManager.setSelectedContent(content);
                                if (editor != null) {
                                    IdeFocusManager.findInstance().requestFocus(editor.getContentComponent(), true);
                                }
                            }
                        }
                        else {
                            PythonConsoleToolWindow consoleToolWindow = PythonConsoleToolWindow.getInstance(project);
                            ToolWindow toolWindow = consoleToolWindow != null ? consoleToolWindow.getToolWindow() : null;
                            if (toolWindow != null && !toolWindow.isVisible()) {
                                toolWindow.show(null);
                                ContentManager contentManager = toolWindow.getContentManager();
                                Content content = contentManager.findContent(descriptor.getDisplayName());
                                if (content != null) {
                                    contentManager.setSelectedContent(content);
                                }
                            }
                        }
                    }
                });
    }

    private static Collection<RunContentDescriptor> getConsoles(Project project) {
        PythonConsoleToolWindow toolWindow = PythonConsoleToolWindow.getInstance(project);

        if (toolWindow != null && toolWindow.getToolWindow().isVisible()) {
            RunContentDescriptor selectedContentDescriptor = toolWindow.getSelectedContentDescriptor();
            return selectedContentDescriptor != null ? Lists.newArrayList(selectedContentDescriptor) : Lists.newArrayList();
        }

        Collection<RunContentDescriptor> descriptors =
                ExecutionHelper.findRunningConsole(project, dom -> dom.getExecutionConsole() instanceof PyCodeExecutor && isAlive(dom));

        if (descriptors.isEmpty() && toolWindow != null) {
            return toolWindow.getConsoleContentDescriptors();
        }
        else {
            return descriptors;
        }
    }

    private static boolean isAlive(RunContentDescriptor dom) {
        ProcessHandler processHandler = dom.getProcessHandler();
        return processHandler != null && !processHandler.isProcessTerminated();
    }

    public static void findCodeExecutor(@NotNull AnActionEvent e,
                                        @NotNull Consumer<PyCodeExecutor> consumer,
                                        @Nullable Editor editor,
                                        @Nullable Project project,
                                        @Nullable Module module) {
        if (project != null) {
            if (canFindConsole(e)) {
                selectConsole(e.getDataContext(), project, consumer, editor);
            }
            else {
                startConsole(project, consumer, module);
            }
        }
    }

    private static void startConsole(final Project project,
                                     final Consumer<PyCodeExecutor> consumer,
                                     Module context) {
        final PythonConsoleToolWindow toolWindow = PythonConsoleToolWindow.getInstance(project);

        if (toolWindow != null && toolWindow.getConsoleContentDescriptors().size() > 0) {
            toolWindow.activate(() -> {
                List<RunContentDescriptor> descs = toolWindow.getConsoleContentDescriptors();

                RunContentDescriptor descriptor = descs.get(0);
                if (descriptor != null && descriptor.getExecutionConsole() instanceof PyCodeExecutor) {
                    consumer.consume((PyCodeExecutor)descriptor.getExecutionConsole());
                }
            });
        }
        else {
            PythonConsoleRunnerFactory consoleRunnerFactory = PythonConsoleRunnerFactory.getInstance();
            PydevConsoleRunner runner = consoleRunnerFactory.createConsoleRunner(project, null);
            runner.addConsoleListener(new PydevConsoleRunner.ConsoleListener() {
                @Override
                public void handleConsoleInitialized(LanguageConsoleView consoleView) {
                    if (consoleView instanceof PyCodeExecutor) {
                        consumer.consume((PyCodeExecutor)consoleView);
                        if (toolWindow != null) {
                            toolWindow.getToolWindow().show(null);
                        }
                    }
                }
            });
            runner.run();
        }
    }

    private static boolean canFindConsole(AnActionEvent e) {
        Project project = e.getProject();
        if (project != null) {
            Collection<RunContentDescriptor> descriptors = getConsoles(project);
            return descriptors.size() > 0;
        }
        else {
            return false;
        }
    }

    private static void executeInConsole(@NotNull PyCodeExecutor codeExecutor, @Nullable String text, Editor editor) {
        codeExecutor.executeCode(text, editor);
    }
}
