$(document).ready(function () {
  $("dt").click(function () {    
    $(this).next("dd").toggleClass("open");    
    $(this).toggleClass("open");
    
    var hasAllOpenStats = $("dd.open").length == $("dd").length;
    var hasNoOpenStats = $("dd.open").length === 0;
    if (hasAllOpenStats) {
      $(".expandobot").removeClass("on");
    }
    if (hasNoOpenStats) {
      $(".expandobot").addClass("on");
    }
  });
  
  /* button expand all */

  $(".expando").click(function () {
       $("dt").addClass("open");
       $("dd").addClass("open");
       $(this).parent().removeClass("on");
    });
  $(".collapse").click(function () {
       $("dt").removeClass("open");
       $("dd").removeClass("open");
       $(this).parent().addClass("on");
    });
});