using System.Text.Json.Nodes;
namespace Hawa.Shared;

internal static class JsonCompatibility
{
    internal static JsonNode DeepClone(this JsonNode node) => JsonNode.Parse(node.ToJsonString())!;
}
