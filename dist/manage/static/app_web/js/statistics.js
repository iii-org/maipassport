'user strict'
$(window).on('load', function () {
    /* swiper slider carousel */
    var swiper = new Swiper('.icon-slide', {
        slidesPerView: 'auto',
        spaceBetween: 0,
    });
    var swiper = new Swiper('.offer-slide', {
        slidesPerView: 'auto',
        spaceBetween: 0,
    });

    var swiper = new Swiper('.two-slide', {
        slidesPerView: 2,
        spaceBetween: 0,
        pagination: {
            el: '.swiper-pagination',
        },
    });

    var swiper = new Swiper('.news-slide', {
        slidesPerView: 5,
        spaceBetween: 0,
        pagination: {
            el: '.swiper-pagination',
        },
        breakpoints: {
            1024: {
                slidesPerView: 4,
                spaceBetween: 0,
            },
            768: {
                slidesPerView: 3,
                spaceBetween: 0,
            },
            640: {
                slidesPerView: 2,
                spaceBetween: 0,
            },
            320: {
                slidesPerView: 2,
                spaceBetween: 0,
            }
        }
    });


    /* chart js charts   */
    var ctx = document.getElementById("linechart").getContext('2d');

    var gradient2 = ctx.createLinearGradient(0, 0, 0, 200);
    gradient2.addColorStop(0, 'rgba(151, 94, 251, 0.40)');
    gradient2.addColorStop(1, 'rgba(91, 168, 255, 0.40)');

    var myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ["一", "二", "三", "四", "五", "六", "日"],
            datasets: [{
                label: ' 體溫 ',
                backgroundColor: gradient2,
                data: [36.5, 36.7, 36.8, 36.2, 36.8, 36.3, 36.4],
                borderColor: "rgba(151, 94, 251, 0.40)",
                borderCapStyle: 'butt',
                borderDash: [],
                borderWidth: 3,
                borderDashOffset: 1,
                borderJoinStyle: 'bevel',
                pointBorderColor: "#ffffff",
                pointBackgroundColor: "#7b65f4",
                pointBorderWidth: 1,
                pointHoverRadius: 12,
                pointHoverBackgroundColor: "#7b65f4",
                pointHoverBorderColor: "#ffffff",
                pointHoverBorderWidth: 0,
                pointRadius: 8,
                pointHitRadius: 8,
                    }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            title: {
                display: false,
                text: 'Chart.js  Line Chart',
            },
            legend: {
                display: false,
                labels: {
                    fontColor: "#888888"
                }
            },
            scales: {
                yAxes: [{
                    display: false,
                    ticks: {
                        fontColor: "#888888",
                        beginAtZero: true,
                        min:30,
                        max:43,
                        stepSize:.001
                    },
                    gridLines: {
                        color: "rgba(160,160,160,0.1)",
                        zeroLineColor: "rgba(160,160,160,0.15)"
                    }
                        }],
                xAxes: [{
                    display: false,
                    ticks: {
                        fontColor: "#888888"
                    },
                    gridLines: {
                        color: "rgba(160,160,160,0.1)",
                        zeroLineColor: "rgba(160,160,160,0.15)"
                    }
                        }]
            },
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 0,
                    bottom: 0
                }
            }
        }
    });


});
