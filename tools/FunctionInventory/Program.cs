// Syntax inventory only. Coverage comes from instrumented test execution.
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

var rows = new List<object>();
foreach (var file in args.Order())
{
    var tree = CSharpSyntaxTree.ParseText(File.ReadAllText(file), path: file);
    var errors = tree.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToArray();
    if (errors.Length != 0) throw new InvalidDataException(string.Join("\n", errors.Select(e => e.ToString())));
    var root = tree.GetRoot();
    var anonymousCounts = new Dictionary<string, int>();
    var candidates = root.DescendantNodes().Where(n =>
        n is BaseMethodDeclarationSyntax or LocalFunctionStatementSyntax or AccessorDeclarationSyntax or AnonymousFunctionExpressionSyntax ||
        n is PropertyDeclarationSyntax p && p.ExpressionBody != null ||
        n is IndexerDeclarationSyntax i && i.ExpressionBody != null).ToArray();
    foreach (var node in candidates)
    {
        SyntaxNode? body = node switch
        {
            BaseMethodDeclarationSyntax m => (SyntaxNode?)m.Body ?? m.ExpressionBody,
            LocalFunctionStatementSyntax m => (SyntaxNode?)m.Body ?? m.ExpressionBody,
            AccessorDeclarationSyntax a => (SyntaxNode?)a.Body ?? a.ExpressionBody,
            AnonymousFunctionExpressionSyntax a => a.Body,
            PropertyDeclarationSyntax p => p.ExpressionBody,
            IndexerDeclarationSyntax i => i.ExpressionBody,
            _ => null
        };
        var owner = string.Join(".", node.Ancestors().Reverse().Select(n => n switch
        {
            BaseNamespaceDeclarationSyntax ns => ns.Name.ToString(),
            BaseTypeDeclarationSyntax t => t.Identifier.Text,
            MethodDeclarationSyntax m => m.Identifier.Text + m.ParameterList.ToString(),
            ConstructorDeclarationSyntax c => c.Identifier.Text + c.ParameterList.ToString(),
            LocalFunctionStatementSyntax f => f.Identifier.Text + f.ParameterList.ToString(),
            PropertyDeclarationSyntax p => p.Identifier.Text,
            IndexerDeclarationSyntax i => "this" + i.ParameterList.ToString(),
            _ => ""
        }).Where(s => s.Length != 0));
        var signature = body == null ? node.ToString() : node.ToString()[..(body.SpanStart - node.SpanStart)];
        signature = string.Join(" ", signature.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)).TrimEnd(';', ' ');
        if (node is AnonymousFunctionExpressionSyntax)
        {
            anonymousCounts.TryGetValue(owner, out var ordinal);
            anonymousCounts[owner] = ordinal + 1;
            signature = "lambda#" + ordinal + " " + signature;
        }
        // Own tokens only: nested closures cannot cover an enclosing method body.
        var lines = body == null ? Array.Empty<int>() : body.DescendantTokens()
            .Where(t => !candidates.Any(c => c != node && body.Span.Contains(c.Span) && c.Span.Contains(t.Span)))
            .Where(t => !t.IsKind(SyntaxKind.OpenBraceToken) && !t.IsKind(SyntaxKind.CloseBraceToken))
            .Select(t => tree.GetLineSpan(t.Span).StartLinePosition.Line + 1).Distinct().Order().ToArray();
        if (body != null && lines.Length == 0)
            lines = new[] { tree.GetLineSpan(body.Span).StartLinePosition.Line + 1 };
        var tokens = node.DescendantTokens().Select(t => t.RawKind + ":" + t.Text);
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", tokens)))).ToLowerInvariant();
        var span = tree.GetLineSpan(node.Span);
        rows.Add(new {
            path = file.Replace('\\', '/'), language = "C#", name = owner + "." + signature,
            signature, kind = node.Kind().ToString(), line = span.StartLinePosition.Line + 1,
            end_line = span.EndLinePosition.Line + 1, body_lines = lines, fingerprint = hash,
            declaration = body == null,
            visibility = node.ChildTokens().FirstOrDefault(t => t.IsKind(SyntaxKind.PublicKeyword) || t.IsKind(SyntaxKind.PrivateKeyword) || t.IsKind(SyntaxKind.ProtectedKeyword) || t.IsKind(SyntaxKind.InternalKeyword)).Text ?? "implicit",
            summary = string.Join(" ", node.GetLeadingTrivia().Where(t => t.IsKind(SyntaxKind.SingleLineDocumentationCommentTrivia)).Select(t => t.ToString().Trim()))
        });
    }
}
Console.WriteLine(JsonSerializer.Serialize(rows));
