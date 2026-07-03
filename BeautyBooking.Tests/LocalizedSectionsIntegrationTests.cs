using System.Net;
using BeautyBooking.Localization;
using Microsoft.AspNetCore.Mvc.Testing;

namespace BeautyBooking.Tests;

public class LocalizedSectionsIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private static readonly string[] HomeSectionKeys =
    {
        "NavHome",
        "NavAbout",
        "NavServices",
        "NavGallery",
        "NavHours",
        "NavContact",
        "AboutTitle",
        "ServicesTitle",
        "GalleryTitle",
        "HoursTitle",
        "ContactEyebrow",
        "BookingTitle"
    };

    private readonly WebApplicationFactory<Program> _factory;

    public LocalizedSectionsIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    public static IEnumerable<object[]> Languages()
    {
        foreach (var language in SiteText.GetSupportedLanguages())
        {
            yield return new object[] { language };
        }
    }

    [Theory]
    [MemberData(nameof(Languages))]
    public async Task HomePage_RendersAllSectionsInSelectedLanguage(string language)
    {
        using var client = _factory.CreateClient();

        var response = await client.GetAsync($"/home?culture={language}&ui-culture={language}");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var html = await response.Content.ReadAsStringAsync();
        foreach (var key in HomeSectionKeys)
        {
            Assert.Contains(SiteText.Get(key, language), html, StringComparison.Ordinal);
        }
    }

    [Theory]
    [MemberData(nameof(Languages))]
    public async Task RedirectedSectionRoutes_KeepLanguage_AndRenderLocalizedSections(string language)
    {
        using var client = _factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            AllowAutoRedirect = false
        });

        var redirectedRoutes = new Dictionary<string, string>
        {
            ["/services"] = "ServicesTitle",
            ["/gallery"] = "GalleryTitle",
            ["/contact"] = "ContactEyebrow",
            ["/price"] = "ServicesTitle"
        };

        foreach (var route in redirectedRoutes)
        {
            var redirectResponse = await client.GetAsync($"{route.Key}?culture={language}&ui-culture={language}");

            Assert.Equal(HttpStatusCode.Redirect, redirectResponse.StatusCode);
            var location = redirectResponse.Headers.Location?.ToString();
            Assert.False(string.IsNullOrWhiteSpace(location));
            Assert.Contains($"culture={language}", location, StringComparison.Ordinal);
            Assert.Contains($"ui-culture={language}", location, StringComparison.Ordinal);

            var followPath = ToRelativePath(location!);
            var finalResponse = await client.GetAsync(followPath);

            Assert.Equal(HttpStatusCode.OK, finalResponse.StatusCode);
            var html = await finalResponse.Content.ReadAsStringAsync();
            Assert.Contains(SiteText.Get(route.Value, language), html, StringComparison.Ordinal);
        }
    }

    [Theory]
    [MemberData(nameof(Languages))]
    public async Task BookingAndThanksPages_RenderInSelectedLanguage(string language)
    {
        using var client = _factory.CreateClient();

        var routeAndKey = new Dictionary<string, string>
        {
            ["/book"] = "BookPageTitle",
            ["/book/elev"] = "BookStudentOption",
            ["/thanks"] = "ThanksTitle"
        };

        foreach (var page in routeAndKey)
        {
            var response = await client.GetAsync($"{page.Key}?culture={language}&ui-culture={language}");

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            var html = await response.Content.ReadAsStringAsync();
            Assert.Contains(SiteText.Get(page.Value, language), html, StringComparison.Ordinal);
        }
    }

    private static string ToRelativePath(string location)
    {
        if (Uri.TryCreate(location, UriKind.Absolute, out var absoluteUri))
        {
            return absoluteUri.PathAndQuery;
        }

        return location;
    }
}
