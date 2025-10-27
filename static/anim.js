
// Piknik Vakti — Animated Icon helper (non-destructive)
(function(){
  document.addEventListener('touchstart', function(e){
    const chip = e.target.closest && e.target.closest('.chip'); if(!chip) return;
    chip.classList.add('is-tap'); setTimeout(()=>chip.classList.remove('is-tap'), 250);
  }, {passive:true});
  const breathing = document.querySelectorAll('.chip.is-breathing');
  breathing.forEach((el, i)=>{ el.style.animationDelay = (i*0.25)+'s'; });
})();
