using BeautyBooking.Controllers;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Localization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;

namespace BeautyBooking.Tests;

public class SectionRedirectControllerTests
{
    [Theory]
    [InlineData("fr")]
    [InlineData("de")]
    [InlineData("zh")]
    [InlineData("ar")]
    [InlineData("fa")]
    public void ServicesRedirect_KeepsCurrentCulture(string culture)
    {
        var controller = new ServicesController(NullLogger<ServicesController>.Instance)
        {
            ControllerContext = BuildControllerContext(culture)
        };

        var result = Assert.IsType<RedirectResult>(controller.Index());
        Assert.Equal($"/home?culture={culture}&ui-culture={culture}#services", result.Url);
    }

    [Theory]
    [InlineData("fr")]
    [InlineData("de")]
    [InlineData("zh")]
    [InlineData("ar")]
    [InlineData("fa")]
    public void GalleryRedirect_KeepsCurrentCulture(string culture)
    {
        var controller = new GalleryController(NullLogger<GalleryController>.Instance)
        {
            ControllerContext = BuildControllerContext(culture)
        };

        var result = Assert.IsType<RedirectResult>(controller.Index());
        Assert.Equal($"/home?culture={culture}&ui-culture={culture}#gallery", result.Url);
    }

    [Theory]
    [InlineData("fr")]
    [InlineData("de")]
    [InlineData("zh")]
    [InlineData("ar")]
    [InlineData("fa")]
    public void ContactRedirect_KeepsCurrentCulture(string culture)
    {
        var controller = new ContactController(NullLogger<ContactController>.Instance)
        {
            ControllerContext = BuildControllerContext(culture)
        };

        var result = Assert.IsType<RedirectResult>(controller.Index());
        Assert.Equal($"/home?culture={culture}&ui-culture={culture}#contact", result.Url);
    }

    [Theory]
    [InlineData("fr")]
    [InlineData("de")]
    [InlineData("zh")]
    [InlineData("ar")]
    [InlineData("fa")]
    public void PriceRedirect_KeepsCurrentCulture(string culture)
    {
        var controller = new PriceController(NullLogger<PriceController>.Instance)
        {
            ControllerContext = BuildControllerContext(culture)
        };

        var result = Assert.IsType<RedirectResult>(controller.Index());
        Assert.Equal($"/home?culture={culture}&ui-culture={culture}#services", result.Url);
    }

    private static ControllerContext BuildControllerContext(string culture)
    {
        var context = new DefaultHttpContext();
        context.Features.Set<IRequestCultureFeature>(
            new RequestCultureFeature(new RequestCulture(culture), provider: null));

        return new ControllerContext
        {
            HttpContext = context
        };
    }
}
