using BeautyBooking.Models;
using Microsoft.AspNetCore.Localization;
using Microsoft.AspNetCore.Mvc;
using System.Diagnostics;

namespace BeautyBooking.Controllers
{
    public class GalleryController : Controller
    {
        private readonly ILogger<GalleryController> _logger;

        public GalleryController(ILogger<GalleryController> logger)
        {
            _logger = logger;
        }

        public IActionResult Index()
        {
            var language = HttpContext.Features.Get<IRequestCultureFeature>()?.RequestCulture.UICulture.TwoLetterISOLanguageName ?? "da";
            return Redirect($"/home?culture={language}&ui-culture={language}#gallery");
        }

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
        }
    }
}
