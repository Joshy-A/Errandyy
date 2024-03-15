var form = document.getElementById('create-errand-form');
var display = 1;


function hideShow() {
    if(display == 1){
        form.style.display = "block";
        display = 0;
    }
    else {
        form.style.display = "none";
        display = 1;
    }
}