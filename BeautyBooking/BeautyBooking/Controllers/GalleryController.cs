using BeautyBooking.Models;
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
            return View("Gallery");
        }

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
        }
    }
}
