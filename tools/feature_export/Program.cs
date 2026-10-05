using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using LiteDB;

// Run against copies of Playnite's database files, never the active library.
if (args.Length != 2) throw new ArgumentException("Usage: FeatureExport SNAPSHOT_DIRECTORY OUTPUT_JSON");
IEnumerable<BsonDocument> Read(string filename)
{
    using var database = new LiteDatabase($"Filename={Path.Combine(args[0], filename)};Read Only=true");
    return database.GetCollectionNames()
        .SelectMany(name => database.GetCollection(name).FindAll()).ToList();
}
string Id(BsonValue value) => value.IsGuid ? value.AsGuid.ToString() : value.AsString;
var features = Read("features.db").ToDictionary(doc => Id(doc["_id"]), doc => doc["Name"].AsString);
var result = new Dictionary<string, List<string>>();
foreach (var game in Read("games.db"))
{
    var names = new List<string>();
    if (game["FeatureIds"].IsArray)
        foreach (var feature in game["FeatureIds"].AsArray)
            if (features.TryGetValue(Id(feature), out var name)) names.Add(name);
    result[Id(game["_id"])] = names;
}
File.WriteAllText(args[1], System.Text.Json.JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"Exported features for {result.Count} games.");
