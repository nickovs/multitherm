Vue.component('thermo-override', {
    props: ['state'],
    template: `
        <div class="override-buttons">
	<span class="or-button" v-bind:class="(state == 0) ? 'or-selected' : ''" v-on:click="offClick" >Off </span><span class="or-button" v-bind:class="(state == null) ? 'or-selected' : ''" v-on:click="autoClick" >Auto</span><span class="or-button" v-bind:class="(state == 1) ? 'or-selected' : ''" v-on:click="onClick" > On </span>
	</div>`,
    methods: {
	offClick: function() {
	    console.log("Off clicked");
	    this.$parent.setOverride(0);
	},
	autoClick: function() {
	    console.log("Auto clicked");
	    this.$parent.setOverride(-1);
	},
	onClick: function() {
	    console.log("On clicked");
	    this.$parent.setOverride(1);
	}
    }
});

Vue.component('thermostat', {
    props: ['display'],
    template: `
	<span class="thermostat" v-bind:id="\'thermo-\'+display.channel_id" v-on:setOverride="setOverride">
	<span class="roomname">{{ display.roomname }}</span><br>
	<span class="currenttemp">{{ display.t }}&deg;{{display.unit}}</span> <br>
	<span class="setpoint"><img v-on:click="decSetPoint" src="/static/minus.png">{{ display.set }}&deg;{{display.unit}}<img v-on:click="incSetPoint" src="/static/plus.png"></span>
	<thermo-override v-bind:state="display.override"></thermo-override>
	</span>
	`,
    methods: {
	incSetPoint: function() {
	    // console.log("Inc");
	    this.display.set += 1;
	    this.display.set_lock = 1;
	    this.scheduleUpdate();
	},
	decSetPoint: function() {
	    // console.log("Dnc");
	    this.display.set -= 1;
	    this.display.set_lock = 1;
	    this.scheduleUpdate();
	},
	scheduleUpdate: function() {
	    if (this.timeout) {
		clearTimeout(this.timeout);
	    }
	    this.timeout = setTimeout(this.updateSetPoint, 500);
	},
	updateSetPoint: function() {
	    var args = {setpoint: control_temp(this.display.set)};
	    console.log(args);
	    axios.post("/thermostat/"+this.display.channel_id, args)
		.then(function(response) {
		    d = display_info_for_state(response.data);
		    thermo_app.display_info.splice(d.channel_id, 1, d);
		})
		.catch(function (error) {
		    console.log(error);
		});
	    this.display.set_lock = 0;
	    this.timeout = 0;
	},
	setOverride: function(new_state) {
	    console.log("setting override to: "+new_state+" for channel: "+this.display.channel_id);
	    var args = {override: new_state};
	    console.log(args);
	    axios.post("/thermostat/"+this.display.channel_id, args)
		.then(function(response) {
		    d = display_info_for_state(response.data);
		    thermo_app.display_info.splice(d.channel_id, 1, d);
		})
		.catch(function (error) {
		    console.log(error);
		});
	}
    }
})

var show_in_C = 0;

function display_temp(t) {
    if (show_in_C == 0) {
	return Math.round((t * 1.8) + 32);
    } else {
	return Math.round(t);
    }
}

function control_temp(t) {
    if (show_in_C == 0) {
	return ((t-32)/1.8);
    } else {
	return t;
    }
}
		  
function display_info_for_state(s) {
    return {out:s.out,
	    t:display_temp(s.t),
	    set:display_temp(s.set),
	    roomname:s.roomname,
	    unit: (show_in_C ? "C" : "F"),
	    channel_id: s.ID,
	    override: s.override
	   }
}

function merge_state_with_lock(old_state, new_state) {
    var res = {};
    for (var attr in old_state) {
	res[attr] = old_state[attr];
    }
    var lock = old_state.set_lock;
    for (var attr in new_state) {
	if (attr != "set" || !lock) {
	    res[attr] = new_state[attr];
	}
    }
    return res;
}

function reload_states() {
    axios.get("/thermostats/all_states")
	.then(function(response) {
	    for (item in response.data.all_states) {
		d = display_info_for_state(response.data.all_states[item]);
		d = merge_state_with_lock(thermo_app.display_info[item], d);
		thermo_app.display_info.splice(item, 1, d);
	    }
	}).catch(function (error) {
	    console.log(error);
	});
}

function reload_timer() {
    reload_states()
    setTimeout(reload_timer, 10*1000);
}

var thermo_app = new Vue({
    el: '#thermostats',
    data: {
	display_info: []
    },
    created: function() {
	axios.get("/thermostats/all_states")
	    .then(function(response) {
		while (thermo_app.display_info.length) {
		    thermo_app.display_info.pop();
		}
		for (item in response.data.all_states) {
		    d = display_info_for_state(response.data.all_states[item]);
		    d.set_lock = 0;
		    thermo_app.display_info.push(d);
		}
		setTimeout(reload_timer, 10*1000);
	    })
	    .catch(function (error) {
		console.log(error);
	    });
    }
})


