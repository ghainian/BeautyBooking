// -----------------------------------------------------------------------------
// Main Javascript 
// -----------------------------------------------------------------------------
(function($) {
    "use strict";

    // Preloader
    // ----------------------------------------
    $(window).on('load', function(){
        if($('#preloader').length > 0){
            $('#preloader').fadeOut('slow',function(){$(this).remove();});
        }
    });

    $(document).on('ready', function() {  

        // Animating the navbar toggle
        // ----------------------------------------
        $('.navbar-toggle').on('click', function () {
            $(this).toggleClass('active');
        });

        // Bootstrap Dropdown on hover
        // ----------------------------------------
        $('.dropdown').on({
            mouseenter: function (){
                $(this).addClass('open');
            },
            mouseleave: function(){
                $(this).removeClass('open');
            }
        });

        // Gallery Filtering
        // ----------------------------------------
        if($('.filter').length > 0){
            $(".filter").on("click", function () {
                var $this = $(this);
                // if we click the active tab, do nothing
                if ( !$this.hasClass("active") ) {
                    $(".filter").removeClass("active");
                    $this.addClass("active"); // set the active tab
                    // get the data-rel value from selected tab and set as filter
                    var $filter = $this.data("rel");
                    // if we select view all, return to initial settings and show all
                    $filter == 'all' ?
                        $(".item")
                        .css('opacity', 1)
                    : // otherwise
                        $(".item")
                        .css('opacity', .2)
                        .filter(function () {
                            // set data-filter value as the data-rel value of selected tab
                            return $(this).data("filter") == $filter;
                        })
                        .css('opacity', 1);
                } // if
            });
        }

        // Sliders
        // ----------------------------------------

        // home splash slider
        if($('.splash-slider').length > 0){
            $('.splash-slider').owlCarousel({
                singleItem: true,
                transitionStyle: 'fade',
                slideSpeed: 1000,
                autoPlay: 5000,
                mouseDrag: false,
                pagination: true,
                navigation: false
            });
        }

        if($('.testimonials-slider').length > 0){
            $('.testimonials-slider').owlCarousel({
                singleItem: true,
                transitionStyle: 'fade',
                slideSpeed: 1000,
                autoPlay: 5000,
                mouseDrag: false,
                pagination: true,
                navigation: false
            });
        }

        // simple gallery slider
        if($('.gallery-slider').length > 0){
            $('.gallery-slider').owlCarousel({
                singleItem: true,
                slideSpeed: 1000,
                autoPlay: 5000,
                mouseDrag: false,
                pagination: true
            });
        }

        // full width gallery slider
        if($('.full-gallery-slider').length > 0){
            $('.full-gallery-slider').owlCarousel({
                itemsDesktop: [1199,4],
                itemsDesktopSmall: [992,3],
                itemsTablet: [768,3],
                itemsMobile: [479,1],
                slideSpeed: 1000,
                autoPlay: 5000,
                pagination: false,
                navigation: true,
                navigationText: ["<i class='fa fa-chevron-left'></i>","<i class='fa fa-chevron-right'></i>"]
            });
        }

        // testimonials slider
        if($('.popup-video').length > 0){
            $('.popup-video ').owlCarousel({
                singleItem: true,
                transitionStyle: 'fade',
                slideSpeed: 1000,
                autoPlay: 5000,
                mouseDrag: false,
                pagination: true,
                navigation: false
            });
        }

        // Progress
        // ----------------------------------------
        if($('.progress-circle').length > 0){
            $('.progress-circle').circleProgress({
                size: 140,
                startAngle: -Math.PI / 2,
                thickness: 30,
                emptyFill: "#fff",
                fill: {
                    color: "#dcb879"
                }
            });
        }

        // Gallery Popup
        // ----------------------------------------

        // image popup
        if($('.popup').length > 0){
            $('.popup').magnificPopup({
              type: 'image'
            });
        }

        // video popup
        if($('.popup-video').length > 0){
            $('.popup-video').magnificPopup({
                type: 'iframe'
            });
        }
    });
})(jQuery);



